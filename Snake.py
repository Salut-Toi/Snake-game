import pygame, sys, random, os, re
from pygame.math import Vector2
import db

# --- DB ---
db.init_db()

# --- Joueur courant ---
current_player_id = None
current_player_name = None

pygame.init()

# --- Couleurs ---
GREEN = (173, 204, 96)
DARK_GREEN = (43, 51, 24)
WHITE = (255, 255, 255)
LIGHT_ACTIVE_GREEN = (140, 190, 90)  # actif pour les boutons de vitesse

# --- Validation pseudo ---
ALLOWED_USERNAME_RE = re.compile(r"^[A-Za-z0-9 _-]{3,20}$")

# --- Grille ---
number_of_cells = 25
GRID_SCALE = 0.86   # la grille prend ~86% du côté court -> marge pour HUD

# --- Fenêtre initiale ---
BASE_SIDE = 900
screen = pygame.display.set_mode((BASE_SIDE, BASE_SIDE), pygame.RESIZABLE)
pygame.display.set_caption("Snake Game")
clock = pygame.time.Clock()
screen_rect = screen.get_rect()

# --- Images ---
base_path = os.path.dirname(__file__)
apple_path = os.path.join(base_path, "images", "apple.png")
apple_raw = pygame.image.load(apple_path).convert_alpha()
apple_raw.set_colorkey(apple_raw.get_at((0, 0)))

logo_path = os.path.join(base_path, "images", "snake.png")
logo_raw = pygame.image.load(logo_path).convert_alpha() if os.path.exists(logo_path) else None

border_path = os.path.join(base_path, "images", "border.png")
border_raw = pygame.image.load(border_path).convert_alpha() if os.path.exists(border_path) else None

# Décor
BORDER_INSET_SRC = 128
BORDER_OVERSHOOT = 1.08

def clamp(v, lo, hi): return max(lo, min(hi, v))

def make_fonts(scale: float):
    title = int(clamp(72 * scale, 36, 120))
    score = int(clamp(40 * scale, 24, 72))
    ui    = int(clamp(38 * scale, 22, 56))
    return (pygame.font.Font(None, title),
            pygame.font.Font(None, score),
            pygame.font.Font(None, ui))

title_font, score_font, ui_font = make_fonts(1.0)

# --- Tailles dynamiques ---
cell_size = 30
board_size = cell_size * number_of_cells
offset_x = (screen_rect.w - board_size) // 2
offset_y = (screen_rect.h - board_size) // 2

# --- Surfaces dépendantes ---
food_surface = None
logo_surface = None

def rescale_assets():
    global food_surface, logo_surface
    food_surface = pygame.transform.smoothscale(apple_raw, (cell_size, cell_size))
    if logo_raw:
        side = int(clamp(cell_size * 4.2, 70, 200))
        logo_surface = pygame.transform.smoothscale(logo_raw, (side, side))
    else:
        logo_surface = None

def compute_layout_for_window(w, h):
    global cell_size, board_size, offset_x, offset_y, title_font, score_font, ui_font
    usable_side = int(min(w, h) * GRID_SCALE)
    cell_size = max(12, usable_side // number_of_cells)
    board_size = cell_size * number_of_cells
    offset_x = (w - board_size) // 2
    offset_y = (h - board_size) // 2
    scale_ui = min(w / BASE_SIDE, h / BASE_SIDE)
    title_font, score_font, ui_font = make_fonts(scale_ui)
    rescale_assets()

def screen_fit_rect():
    return pygame.Rect(0, 0, screen_rect.w, screen_rect.h)

def draw_border_at_rect(rect):
    if not border_raw or rect is None:
        return
    scaled = pygame.transform.smoothscale(border_raw, (rect.w, rect.h))
    screen.blit(scaled, rect.topleft)

def draw_fullscreen_border_with_board_hole():
    if not border_raw:
        return
    draw_border_at_rect(screen_fit_rect())
    pygame.draw.rect(screen, GREEN, (offset_x, offset_y, board_size, board_size))

# --- Texte avec contour ---
def blit_text_with_outline_topleft(surface, text, font, main_color, outline_color, x, y, thickness=2):
    base = font.render(text, True, main_color)
    outline = font.render(text, True, outline_color)
    for dx in (-thickness, 0, thickness):
        for dy in (-thickness, 0, thickness):
            if dx == 0 and dy == 0: continue
            surface.blit(outline, (x + dx, y + dy))
    surface.blit(base, (x, y))

def blit_text_with_outline_topright(surface, text, font, main_color, outline_color, x, y, thickness=2):
    base = font.render(text, True, main_color)
    outline = font.render(text, True, outline_color)
    base_rect = base.get_rect(topright=(x, y))
    for dx in (-thickness, 0, thickness):
        for dy in (-thickness, 0, thickness):
            if dx == 0 and dy == 0: continue
            r = outline.get_rect(topright=(x + dx, y + dy))
            surface.blit(outline, r.topleft)
    surface.blit(base, base_rect.topleft)

def blit_text_with_outline_center(surface, text, font, main_color, outline_color, center, thickness=2):
    base = font.render(text, True, main_color)
    outline = font.render(text, True, outline_color)
    rect = base.get_rect(center=center)
    for dx in (-thickness, 0, thickness):
        for dy in (-thickness, 0, thickness):
            if dx == 0 and dy == 0: continue
            r = outline.get_rect(center=(center[0] + dx, center[1] + dy))
            surface.blit(outline, r)
    surface.blit(base, rect)

# --- Paramètres Gameplay (persistés) ---
SPEED_INTERVALS = {"facile": 220, "normal": 180, "difficile": 140}
current_speed = db.get_setting("speed", "normal")
if current_speed not in SPEED_INTERVALS:
    current_speed = "normal"
wrap_walls = db.get_setting("wrap_walls", "0") == "1"

# --- États ---
# MENU | PLAYING | LEADERBOARD | PAUSED | HELP_MENU
app_state = "MENU"

# =========================
#        UI widgets
# =========================
class Button:
    def __init__(self, rect, text, font, bg_color, text_color, hover_color=None, radius=10):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.bg = bg_color
        self.fg = text_color
        self.hover = hover_color or bg_color
        self.radius = radius
    def set_rect(self, rect): self.rect = pygame.Rect(rect)
    def set_font(self, font): self.font = font
    def draw(self, surface, override_bg=None):
        mouse = pygame.mouse.get_pos()
        base_col = override_bg if override_bg is not None else self.bg
        color = self.hover if self.rect.collidepoint(mouse) else base_col
        pygame.draw.rect(surface, color, self.rect, border_radius=self.radius)
        label = self.font.render(self.text, True, self.fg)
        surface.blit(label, label.get_rect(center=self.rect.center))
    def is_clicked(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)

class Toggle:
    def __init__(self, rect, font, label, on=False):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.label = label
        self.on = on
    def set_rect(self, rect): self.rect = pygame.Rect(rect)
    def set_font(self, font): self.font = font
    def draw(self, surface):
        label_surf = self.font.render(self.label, True, DARK_GREEN)
        label_rect = label_surf.get_rect(midleft=(self.rect.x + 8, self.rect.centery))
        surface.blit(label_surf, label_rect)
        sw_h = self.rect.h
        sw_w = int(sw_h * 1.7)
        sw_x = self.rect.right - sw_w
        sw_y = self.rect.y
        pygame.draw.rect(surface, (90, 150, 90) if self.on else (160, 160, 160),
                         (sw_x, sw_y, sw_w, sw_h), border_radius=sw_h//2)
        knob_r = sw_h//2 - 3
        cx = sw_x + (sw_h//2 if not self.on else sw_w - sw_h//2)
        pygame.draw.circle(surface, WHITE, (cx, sw_y + sw_h//2), knob_r)
    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on = not self.on
                return True
        return False

class TextInput:
    def __init__(self, rect, font, text_color, bg_color, border_color,
                 placeholder="Entrez votre pseudo", radius=8):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.text_color = text_color
        self.bg_color = bg_color
        self.border_color = border_color
        self.radius = radius
        self.text = ""
        self.placeholder = placeholder
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0
    def set_rect(self, rect): self.rect = pygame.Rect(rect)
    def set_font(self, font): self.font = font
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                return "submit"
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                if len(event.unicode) == 1 and (event.unicode.isalnum() or event.unicode in "_ -"):
                    if len(self.text) < 20:
                        self.text += event.unicode
        return None
    def update(self, dt):
        self.cursor_timer += dt
        if self.cursor_timer > 500:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
    def draw(self, surface):
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=self.radius)
        pygame.draw.rect(surface, self.border_color, self.rect, width=2, border_radius=self.radius)
        label = self.font.render(self.text or self.placeholder, True,
                                 self.text_color if self.text else (120,120,120))
        surface.blit(label, (self.rect.x + 10, self.rect.y + (self.rect.height - label.get_height()) // 2))
        if self.active and self.cursor_visible and self.text:
            cx = self.rect.x + 10 + self.font.size(self.text)[0]
            pygame.draw.line(surface, self.text_color, (cx, self.rect.y + 8), (cx, self.rect.bottom - 8), 2)

# =========================
#         Jeu
# =========================
class Food:
    def __init__(self, snake_body):
        self.position = self.generate_random_position(snake_body)
    def draw(self):
        x = int(self.position.x * cell_size + offset_x)
        y = int(self.position.y * cell_size + offset_y)
        screen.blit(food_surface, (x, y))
    def generate_random_cell(self):
        return Vector2(random.randint(0, number_of_cells - 1),
                       random.randint(0, number_of_cells - 1))
    def generate_random_position(self, snake_body):
        p = self.generate_random_cell()
        while p in snake_body:
            p = self.generate_random_cell()
        return p

class Snake:
    def __init__(self):
        self.body = [Vector2(6, 9), Vector2(5, 9), Vector2(4, 9)]
        self.direction = Vector2(1, 0)
        self.new_block = False
    def draw(self):
        for segment in self.body:
            rect = (offset_x + segment.x * cell_size,
                    offset_y + segment.y * cell_size,
                    cell_size, cell_size)
            pygame.draw.rect(screen, DARK_GREEN, rect, 0, 6)
    def update(self):
        self.body.insert(0, self.body[0] + self.direction)
        if not self.new_block:
            self.body = self.body[:-1]
        else:
            self.new_block = False
    def reset(self):
        self.body = [Vector2(6, 9), Vector2(5, 9), Vector2(4, 9)]
        self.direction = Vector2(1, 0)

class Game:
    def __init__(self):
        self.snake = Snake()
        self.food = Food(self.snake.body)
        self.state = "STOPPED"
        self.score = 0
    def draw(self):
        self.snake.draw()
        self.food.draw()
    def update(self):
        if self.state == "PLAYING":
            self.snake.update()
            self.apply_wrap_or_check_wall()
            self.check_collision_with_food()
            self.check_self_collision()
    def apply_wrap_or_check_wall(self):
        head = self.snake.body[0]
        if wrap_walls:
            if head.x < 0: head.x = number_of_cells - 1
            elif head.x >= number_of_cells: head.x = 0
            if head.y < 0: head.y = number_of_cells - 1
            elif head.y >= number_of_cells: head.y = 0
            self.snake.body[0] = head
        else:
            if head.x in (-1, number_of_cells) or head.y in (-1, number_of_cells):
                self.game_over()
    def check_collision_with_food(self):
        if self.snake.body[0] == self.food.position:
            self.food.position = self.food.generate_random_position(self.snake.body)
            self.snake.new_block = True
            self.score += 1
    def check_self_collision(self):
        if self.snake.body[0] in self.snake.body[1:]:
            self.game_over()
    def game_over(self):
        global app_state
        try:
            db.record_run(self.score, current_player_id)
        except Exception as e:
            print("DB error:", e)
        self.snake.reset()
        self.food.position = self.food.generate_random_position(self.snake.body)
        self.state = "STOPPED"
        self.score = 0
        app_state = "MENU"

# =========================
#        Écrans
# =========================
class MenuScreen:
    def __init__(self, screen_rect, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        self.screen_rect = screen_rect

        self.input = TextInput(pygame.Rect(0,0,10,10), ui_font, DARK_GREEN, (240,245,230), DARK_GREEN)
        self.start_btn   = Button(pygame.Rect(0,0,10,10), "Démarrer",    ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.leader_btn  = Button(pygame.Rect(0,0,10,10), "Leaderboard", ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.help_btn    = Button(pygame.Rect(0,0,10,10), "Aide",        ui_font, DARK_GREEN, (255,255,255), (60,72,35))

        self.speed_easy   = Button(pygame.Rect(0,0,10,10),  "Facile",     ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.speed_normal = Button(pygame.Rect(0,0,10,10),  "Normal",     ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.speed_hard   = Button(pygame.Rect(0,0,10,10),  "Difficile",  ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.wrap_toggle  = Toggle(pygame.Rect(0,0,10,10), ui_font, "Bords traversables", on=wrap_walls)

        self.message = ""
        self.relayout(screen_rect)

    def relayout(self, r):
        self.screen_rect = r
        w, h = r.size

        # >>> Espacements augmentés
        title_y   = int(h * 0.06)
        logo_y    = int(h * 0.14)     # LOGO
        speed_y   = int(h * 0.26)     # rangée des vitesses (plus bas)
        toggle_y  = int(h * 0.36)
        input_y   = int(h * 0.46)
        buttons_y = int(h * 0.60)

        # Pseudo
        input_w = int(clamp(w * 0.50, 360, 720))
        input_h = int(clamp(h * 0.06, 40, 78))
        self.input.set_rect(pygame.Rect(r.centerx - input_w // 2, input_y, input_w, input_h))

        # Boutons vitesse — plus espacés
        btn_w = int(clamp(w * 0.15, 130, 220))
        btn_h = int(clamp(h * 0.07,  48, 82))
        spacing = int(clamp(w * 0.03, 18, 48))  # ← espace horizontal augmenté
        total_w = 3 * btn_w + 2 * spacing
        start_x = r.centerx - total_w // 2
        self.speed_easy.set_rect(  pygame.Rect(start_x,                       speed_y, btn_w, btn_h))
        self.speed_normal.set_rect(pygame.Rect(start_x + btn_w + spacing,     speed_y, btn_w, btn_h))
        self.speed_hard.set_rect(  pygame.Rect(start_x + 2*(btn_w + spacing), speed_y, btn_w, btn_h))

        # Toggle wrap centré (hauteur = boutons vitesse)
        toggle_h = btn_h
        toggle_w = int(clamp(w * 0.50, 360, 640))
        self.wrap_toggle.set_rect(pygame.Rect(r.centerx - toggle_w//2, toggle_y, toggle_w, toggle_h))

        # Boutons bas — bien espacés verticalement
        main_btn_w = int(clamp(w * 0.30, 240, 380))
        main_btn_h = btn_h
        gap_y = int(clamp(h * 0.09, 52, 120))   # ← gros écart entre les 3
        self.start_btn.set_rect(  pygame.Rect(r.centerx - main_btn_w // 2, buttons_y,                 main_btn_w, main_btn_h))
        self.leader_btn.set_rect( pygame.Rect(r.centerx - main_btn_w // 2, buttons_y + gap_y,         main_btn_w, main_btn_h))
        self.help_btn.set_rect(   pygame.Rect(r.centerx - main_btn_w // 2, buttons_y + 2 * gap_y,     main_btn_w, main_btn_h))

        # pour draw()
        self._title_y = title_y
        self._logo_center = (r.centerx, logo_y)

    def apply_fonts(self, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        self.input.set_font(ui_font)
        for b in (self.start_btn, self.leader_btn, self.help_btn,
                  self.speed_easy, self.speed_normal, self.speed_hard):
            b.set_font(ui_font)
        self.wrap_toggle.set_font(ui_font)

    def _apply_speed_choice(self, choice: str):
        global current_speed
        if choice not in SPEED_INTERVALS: return
        current_speed = choice
        db.set_setting("speed", choice)
        set_snake_timer(SPEED_INTERVALS[choice])

    def handle_event(self, event):
        s = self.input.handle_event(event)
        if s == "submit":
            return ("START", self.input.text.strip() or None)

        if self.speed_easy.is_clicked(event):   self._apply_speed_choice("facile")
        if self.speed_normal.is_clicked(event): self._apply_speed_choice("normal")
        if self.speed_hard.is_clicked(event):   self._apply_speed_choice("difficile")

        if self.wrap_toggle.is_clicked(event):
            global wrap_walls
            wrap_walls = self.wrap_toggle.on
            db.set_setting("wrap_walls", "1" if wrap_walls else "0")

        if self.start_btn.is_clicked(event):   return ("START", self.input.text.strip() or None)
        if self.leader_btn.is_clicked(event):  return ("LEADERBOARD", None)
        if self.help_btn.is_clicked(event):    return ("HELP_MENU", None)
        return (None, None)

    def update(self, dt): self.input.update(dt)

    def draw(self, surface):
        blit_text_with_outline_center(
            surface, "Snake Game", self.title_font, DARK_GREEN, WHITE,
            (self.screen_rect.centerx, self._title_y), thickness=3
        )
        if logo_surface:
            surface.blit(logo_surface, logo_surface.get_rect(center=self._logo_center))

        # Libellé "Vitesse :" juste sous le logo
        speed_label_y = self._logo_center[1] + int(self.speed_easy.rect.h * 0.9)
        blit_text_with_outline_center(
            surface, "Vitesse :", self.ui_font, DARK_GREEN, WHITE,
            (self.screen_rect.centerx, speed_label_y), thickness=2
        )

        # Boutons Vitesse (vert clair si sélectionné)
        for name, btn in [("facile", self.speed_easy), ("normal", self.speed_normal), ("difficile", self.speed_hard)]:
            active = (current_speed == name)
            color = LIGHT_ACTIVE_GREEN if active else DARK_GREEN
            btn.draw(surface, override_bg=color)

        self.wrap_toggle.draw(surface)
        self.input.draw(surface)
        self.start_btn.draw(surface)
        self.leader_btn.draw(surface)
        self.help_btn.draw(surface)

        if self.message:
            m = self.ui_font.render(self.message, True, (200, 40, 40))
            surface.blit(m, m.get_rect(midtop=(self.screen_rect.centerx, self.input.rect.bottom + 10)))

class LeaderboardScreen:
    def __init__(self, screen_rect, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        self.screen_rect = screen_rect
        self.rows = []
        self.current_period = "daily"
        self.daily_btn   = Button(pygame.Rect(0,0,10,10), "Jour",     ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.weekly_btn  = Button(pygame.Rect(0,0,10,10), "Semaine",  ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.monthly_btn = Button(pygame.Rect(0,0,10,10), "Mois",     ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.back_btn    = Button(pygame.Rect(0,0,10,10), "Retour",   ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.relayout(screen_rect)
        self.load_rows()

    def _layout_period_buttons(self, w, h):
        btn_w = int(clamp(w * 0.15, 130, 220))
        btn_h = int(clamp(h * 0.07,  48, 82))
        spacing = int(clamp(w * 0.03, 18, 48))
        y_base = int(h * 0.18)
        total_w = 3 * btn_w + 2 * spacing
        start_x = (w - total_w) // 2
        self.daily_btn.set_rect(  pygame.Rect(start_x,                       y_base, btn_w, btn_h))
        self.weekly_btn.set_rect( pygame.Rect(start_x + btn_w + spacing,     y_base, btn_w, btn_h))
        self.monthly_btn.set_rect(pygame.Rect(start_x + 2*(btn_w + spacing), y_base, btn_w, btn_h))

    def relayout(self, r):
        self.screen_rect = r
        w, h = r.size
        self._layout_period_buttons(w, h)
        btn_w = int(clamp(w * 0.20, 170, 340))
        btn_h = int(clamp(h * 0.07, 50, 90))
        self.back_btn.set_rect(pygame.Rect(r.centerx - btn_w // 2, h - btn_h - int(h * 0.06), btn_w, btn_h))

    def apply_fonts(self, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        for b in (self.daily_btn, self.weekly_btn, self.monthly_btn, self.back_btn):
            b.set_font(ui_font)

    def handle_event(self, event):
        if self.back_btn.is_clicked(event):
            return "BACK"
        if self.daily_btn.is_clicked(event):
            self.current_period = "daily";  self.load_rows()
        if self.weekly_btn.is_clicked(event):
            self.current_period = "weekly"; self.load_rows()
        if self.monthly_btn.is_clicked(event):
            self.current_period = "monthly"; self.load_rows()
        return None

    def load_rows(self):
        try:
            self.rows = db.leaderboard(self.current_period, 10)
        except Exception as e:
            print("Erreur leaderboard:", e)
            self.rows = []

    def draw(self, surface):
        blit_text_with_outline_center(
            surface, "Classements", self.title_font, DARK_GREEN, WHITE,
            (self.screen_rect.centerx, int(self.screen_rect.height * 0.10)), thickness=3
        )
        for b in (self.daily_btn, self.weekly_btn, self.monthly_btn):
            active = (
                (self.current_period == "daily"   and b.text == "Jour") or
                (self.current_period == "weekly"  and b.text == "Semaine") or
                (self.current_period == "monthly" and b.text == "Mois")
            )
            color = LIGHT_ACTIVE_GREEN if active else DARK_GREEN
            b.draw(surface, override_bg=color)

        y = int(self.screen_rect.height * 0.34)
        line_gap = int(clamp(self.screen_rect.height * 0.06, 36, 78))
        for i, (score, username, created_at) in enumerate(self.rows, 1):
            line = f"{i:>2}. {username:<15} — {score} pts"
            surf = self.ui_font.render(line, True, DARK_GREEN)
            surface.blit(surf, surf.get_rect(midtop=(self.screen_rect.centerx, y)))
            y += line_gap

        if not self.rows:
            empty = self.ui_font.render("Aucun score enregistré.", True, DARK_GREEN)
            surface.blit(empty, empty.get_rect(center=self.screen_rect.center))

        self.back_btn.draw(surface)

class PauseScreen:
    def __init__(self, screen_rect, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        self.screen_rect = screen_rect
        self.resume_btn = Button(pygame.Rect(0,0,10,10), "Reprendre", ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.menu_btn   = Button(pygame.Rect(0,0,10,10), "Menu",      ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.relayout(screen_rect)
        self.lines = [
            "Déplacements : Flèches direction",
            "Pause : P ou bouton Aide    |    Quitter : Échap",
            "Objectif : mangez les pommes pour grandir.",
            "Astuce : ne vous mordez pas la queue !"
        ]
    def relayout(self, r):
        self.screen_rect = r
        w, h = r.size
        btn_w = int(clamp(w * 0.24, 190, 340))
        btn_h = int(clamp(h * 0.075,  52,  96))
        gap_x = int(clamp(w * 0.03, 20, 48))
        y = int(h * 0.72)
        self.resume_btn.set_rect(pygame.Rect(r.centerx - btn_w - gap_x//2, y, btn_w, btn_h))
        self.menu_btn.set_rect(  pygame.Rect(r.centerx + gap_x//2,        y, btn_w, btn_h))
    def apply_fonts(self, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        self.resume_btn.set_font(ui_font)
        self.menu_btn.set_font(ui_font)
    def handle_event(self, event, show_resume: bool):
        if show_resume and self.resume_btn.is_clicked(event):
            return "RESUME"
        if self.menu_btn.is_clicked(event):
            return "MENU"
        if event.type == pygame.KEYDOWN:
            if show_resume and event.key in (pygame.K_ESCAPE, pygame.K_p):
                return "RESUME"
        return None
    def draw(self, surface, show_resume: bool):
        overlay = pygame.Surface((self.screen_rect.w, self.screen_rect.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        surface.blit(overlay, (0,0))
        blit_text_with_outline_center(
            surface, "Aide", self.title_font, DARK_GREEN, WHITE,
            (self.screen_rect.centerx, int(self.screen_rect.height * 0.20)), thickness=3
        )
        y = int(self.screen_rect.height * 0.36)
        gap = int(clamp(self.screen_rect.height * 0.06, 32, 68))
        for txt in self.lines:
            blit_text_with_outline_center(
                surface, txt, self.ui_font, DARK_GREEN, WHITE,
                (self.screen_rect.centerx, y), thickness=2
            )
            y += gap
        if show_resume:
            self.resume_btn.draw(surface)
        self.menu_btn.draw(surface)

# --- HUD aide en jeu (bouton à droite) ---
hud_help_btn = Button(pygame.Rect(0,0,10,10), "? Aide", ui_font, DARK_GREEN, (255,255,255), (60,72,35))

def layout_hud_help():
    w, h = screen_rect.size
    btn_w = int(clamp(w * 0.12, 110, 180))
    btn_h = int(clamp(h * 0.06,  44,  70))
    margin = int(clamp(w * 0.02, 10, 28))
    x = screen_rect.right - margin - btn_w
    y = max(margin, int(offset_y * 0.25))
    hud_help_btn.set_rect(pygame.Rect(x, y, btn_w, btn_h))

# =========================
#   Instanciation & Layout
# =========================
compute_layout_for_window(screen_rect.w, screen_rect.h)
rescale_assets()
game = Game()
menu_screen = MenuScreen(screen_rect, title_font, ui_font)
leader_screen = LeaderboardScreen(screen_rect, title_font, ui_font)
pause_screen = PauseScreen(screen_rect, title_font, ui_font)
layout_hud_help()

# =========================
#    Timer snake (vitesse)
# =========================
SNAKE_UPDATE = pygame.USEREVENT

def set_snake_timer(interval_ms: int):
    pygame.time.set_timer(SNAKE_UPDATE, 0)
    pygame.time.set_timer(SNAKE_UPDATE, interval_ms)

set_snake_timer(SPEED_INTERVALS[current_speed])

# =========================
#        Boucle
# =========================
while True:
    dt = clock.tick(60)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()

        if event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            screen_rect = screen.get_rect()
            compute_layout_for_window(event.w, event.h)
            menu_screen.apply_fonts(title_font, ui_font)
            leader_screen.apply_fonts(title_font, ui_font)
            pause_screen.apply_fonts(title_font, ui_font)
            menu_screen.relayout(screen_rect)
            leader_screen.relayout(screen_rect)
            pause_screen.relayout(screen_rect)
            layout_hud_help()

        if app_state == "MENU":
            action, payload = menu_screen.handle_event(event)
            if action == "START":
                pseudo = (payload or "").strip()
                if not pseudo:
                    menu_screen.message = "Veuillez entrer un pseudo."
                elif not ALLOWED_USERNAME_RE.fullmatch(pseudo):
                    menu_screen.message = "Le pseudo doit faire 3 à 20 caractères (lettres, chiffres, espace, _ ou -)."
                else:
                    try:
                        current_player_name = pseudo
                        current_player_id = db.get_or_create_player(pseudo)
                    except ValueError as e:
                        menu_screen.message = str(e)
                    else:
                        game.state = "PLAYING"
                        app_state = "PLAYING"
                        menu_screen.message = ""
            elif action == "LEADERBOARD":
                leader_screen.load_rows()
                app_state = "LEADERBOARD"
            elif action == "HELP_MENU":
                app_state = "HELP_MENU"

        elif app_state == "LEADERBOARD":
            if leader_screen.handle_event(event) == "BACK":
                app_state = "MENU"

        elif app_state == "PLAYING":
            if hud_help_btn.is_clicked(event):
                app_state = "PAUSED"
            if event.type == SNAKE_UPDATE:
                game.update()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    app_state = "PAUSED"
                if game.state == "STOPPED": game.state = "PLAYING"
                if event.key == pygame.K_UP    and game.snake.direction != Vector2(0, 1):  game.snake.direction = Vector2(0, -1)
                if event.key == pygame.K_DOWN  and game.snake.direction != Vector2(0,-1): game.snake.direction = Vector2(0, 1)
                if event.key == pygame.K_LEFT  and game.snake.direction != Vector2(1, 0):  game.snake.direction = Vector2(-1, 0)
                if event.key == pygame.K_RIGHT and game.snake.direction != Vector2(-1,0): game.snake.direction = Vector2(1, 0)

        elif app_state in ("PAUSED", "HELP_MENU"):
            show_resume = (app_state == "PAUSED")
            nav = pause_screen.handle_event(event, show_resume=show_resume)
            if nav == "RESUME":
                app_state = "PLAYING"
            elif nav == "MENU":
                app_state = "MENU"

    # --- DRAW ---
    screen.fill(GREEN)

    # Fond jungle
    if app_state in ("MENU", "LEADERBOARD", "PAUSED", "HELP_MENU"):
        if border_raw:
            draw_border_at_rect(screen_fit_rect())
    elif app_state == "PLAYING":
        draw_fullscreen_border_with_board_hole()

    # UI / Jeu
    if app_state == "MENU":
        menu_screen.update(dt)
        menu_screen.draw(screen)

    elif app_state == "LEADERBOARD":
        leader_screen.draw(screen)

    elif app_state == "PLAYING":
        pygame.draw.rect(
            screen, DARK_GREEN,
            (offset_x - 5, offset_y - 5, board_size + 10, board_size + 10),
            5
        )
        game.draw()
        hud_y = max(10, int(offset_y * 0.6))
        blit_text_with_outline_topleft(
            screen, "Snake Game", title_font, DARK_GREEN, WHITE,
            offset_x - 5, hud_y, thickness=3
        )
        blit_text_with_outline_topright(
            screen, str(game.score), score_font, DARK_GREEN, WHITE,
            screen_rect.w - offset_x, hud_y, thickness=3
        )
        hud_help_btn.draw(screen)

    elif app_state in ("PAUSED", "HELP_MENU"):
        if app_state == "PAUSED":
            pygame.draw.rect(
                screen, DARK_GREEN,
                (offset_x - 5, offset_y - 5, board_size + 10, board_size + 10),
                5
            )
            hud_y = max(10, int(offset_y * 0.6))
            blit_text_with_outline_topleft(
                screen, "Snake Game", title_font, DARK_GREEN, WHITE,
                offset_x - 5, hud_y, thickness=3
            )
            blit_text_with_outline_topright(
                screen, str(game.score), score_font, DARK_GREEN, WHITE,
                screen_rect.w - offset_x, hud_y, thickness=3
            )
        pause_screen.draw(screen, show_resume=(app_state == "PAUSED"))

    pygame.display.update()
