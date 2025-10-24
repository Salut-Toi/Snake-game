import pygame, sys, random, os
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

logo_path = r"C:\Users\kyman\Snake-game\images\snake.png"
logo_raw = pygame.image.load(logo_path).convert_alpha() if os.path.exists(logo_path) else None

border_path = os.path.join(base_path, "images", "border.png")
border_raw = pygame.image.load(border_path).convert_alpha() if os.path.exists(border_path) else None

# Décor : si border.png fait 1024x1024 et que l’ouverture intérieure démarre à 128px :
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
        side = int(clamp(cell_size * 5, 80, 260))
        logo_surface = pygame.transform.smoothscale(logo_raw, (side, side))
    else:
        logo_surface = None

def compute_layout_for_window(w, h):
    """Grille réduite (GRID_SCALE), centrée ; polices échelonnées ; assets rescalés."""
    global cell_size, board_size, offset_x, offset_y, title_font, score_font, ui_font
    usable_side = int(min(w, h) * GRID_SCALE)
    cell_size = max(12, usable_side // number_of_cells)
    board_size = cell_size * number_of_cells
    offset_x = (w - board_size) // 2
    offset_y = (h - board_size) // 2
    scale_ui = min(w / BASE_SIDE, h / BASE_SIDE)
    title_font, score_font, ui_font = make_fonts(scale_ui)
    rescale_assets()

def compute_border_target_rect():
    """Rect du décor tel que son ouverture colle au board (offset_x/y, board_size)."""
    if not border_raw:
        return None
    W, H = border_raw.get_size()
    inset = BORDER_INSET_SRC
    s_x = board_size / (W - 2*inset)
    s_y = board_size / (H - 2*inset)
    s = min(s_x, s_y) * BORDER_OVERSHOOT
    dest_w = int(W * s)
    dest_h = int(H * s)
    x = int(offset_x - inset * s)
    y = int(offset_y - inset * s)
    return pygame.Rect(x, y, dest_w, dest_h)

def screen_fit_rect():
    return pygame.Rect(0, 0, screen_rect.w, screen_rect.h)

def draw_border_at_rect(rect):
    if not border_raw or rect is None:
        return
    scaled = pygame.transform.smoothscale(border_raw, (rect.w, rect.h))
    screen.blit(scaled, rect.topleft)

def draw_fullscreen_border_with_board_hole():
    """Bordure plein écran + trou central (zone de jeu) peinte en vert champ."""
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

# --- États ---
app_state = "MENU"  # MENU | PLAYING | LEADERBOARD

# =========================
#        UI
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
    def draw(self, surface):
        mouse = pygame.mouse.get_pos()
        color = self.hover if self.rect.collidepoint(mouse) else self.bg
        pygame.draw.rect(surface, color, self.rect, border_radius=self.radius)
        label = self.font.render(self.text, True, self.fg)
        surface.blit(label, label.get_rect(center=self.rect.center))
    def is_clicked(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)

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
            self.check_collision_with_food()
            self.check_fail()
            self.check_self_collision()
    def check_collision_with_food(self):
        if self.snake.body[0] == self.food.position:
            self.food.position = self.food.generate_random_position(self.snake.body)
            self.snake.new_block = True
            self.score += 1
    def check_fail(self):
        h = self.snake.body[0]
        if h.x in (-1, number_of_cells) or h.y in (-1, number_of_cells):
            self.game_over()
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
        self.start_btn = Button(pygame.Rect(0,0,10,10), "Démarrer", ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.leader_btn= Button(pygame.Rect(0,0,10,10), "Leaderboard", ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.message = ""
        self.relayout(screen_rect)
    def relayout(self, r):
        self.screen_rect = r
        w, h = r.size
        input_w = int(clamp(w * 0.5, 320, 720))
        input_h = int(clamp(h * 0.06, 40, 90))
        center_y = int(h * 0.5)
        self.input.set_rect(pygame.Rect(r.centerx - input_w // 2, center_y, input_w, input_h))
        btn_w = int(clamp(w * 0.32, 220, 420))
        btn_h = int(clamp(h * 0.07, 50, 100))
        self.start_btn.set_rect(pygame.Rect(r.centerx - btn_w // 2, center_y + int(h * 0.10), btn_w, btn_h))
        self.leader_btn.set_rect(pygame.Rect(r.centerx - btn_w // 2, center_y + int(h * 0.20), btn_w, btn_h))
    def apply_fonts(self, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        self.input.set_font(ui_font)
        self.start_btn.set_font(ui_font)
        self.leader_btn.set_font(ui_font)
    def handle_event(self, event):
        s = self.input.handle_event(event)
        if s == "submit": return ("START", self.input.text.strip() or None)
        if self.start_btn.is_clicked(event): return ("START", self.input.text.strip() or None)
        if self.leader_btn.is_clicked(event): return ("LEADERBOARD", None)
        return (None, None)
    def update(self, dt): self.input.update(dt)
    def draw(self, surface):
        # Titre centré avec contour blanc
        blit_text_with_outline_center(
            surface, "Snake Game", self.title_font, DARK_GREEN, WHITE,
            (self.screen_rect.centerx, int(self.screen_rect.height * 0.12)), thickness=3
        )
        # Logo
        if logo_surface:
            logo_rect = logo_surface.get_rect(center=(self.screen_rect.centerx, self.input.rect.top - int(self.screen_rect.height * 0.12)))
            surface.blit(logo_surface, logo_rect)
        self.input.draw(surface)
        self.start_btn.draw(surface)
        self.leader_btn.draw(surface)
        if self.message:
            m = self.ui_font.render(self.message, True, (200, 40, 40))
            surface.blit(m, m.get_rect(midtop=(self.screen_rect.centerx, self.input.rect.bottom + 10)))

class LeaderboardScreen:
    def __init__(self, screen_rect, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        self.screen_rect = screen_rect
        self.rows = []
        self.current_period = "daily"  # par défaut : jour

        # Crée des boutons ; placement fait dans relayout()
        self.daily_btn   = Button(pygame.Rect(0,0,10,10), "Jour",     ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.weekly_btn  = Button(pygame.Rect(0,0,10,10), "Semaine",  ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.monthly_btn = Button(pygame.Rect(0,0,10,10), "Mois",     ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.back_btn    = Button(pygame.Rect(0,0,10,10), "Retour",   ui_font, DARK_GREEN, (255,255,255), (60,72,35))

        self.relayout(screen_rect)
        self.load_rows()

    def _layout_period_buttons(self, w, h):
        """Centre les 3 boutons période en haut du leaderboard."""
        btn_w = int(clamp(w * 0.16, 150, 240))
        btn_h = int(clamp(h * 0.07,  48,  88))
        spacing = int(clamp(w * 0.02, 12, 28))
        y_base = int(h * 0.16)

        total_width = 3 * btn_w + 2 * spacing
        start_x = (w - total_width) // 2

        self.daily_btn.set_rect(  pygame.Rect(start_x,                       y_base, btn_w, btn_h))
        self.weekly_btn.set_rect( pygame.Rect(start_x + btn_w + spacing,     y_base, btn_w, btn_h))
        self.monthly_btn.set_rect(pygame.Rect(start_x + 2*(btn_w + spacing), y_base, btn_w, btn_h))

    def relayout(self, r):
        self.screen_rect = r
        w, h = r.size
        self._layout_period_buttons(w, h)

        btn_w = int(clamp(w * 0.18, 160, 320))
        btn_h = int(clamp(h * 0.06, 44, 90))
        self.back_btn.set_rect(pygame.Rect(r.centerx - btn_w // 2, h - btn_h - int(h * 0.05), btn_w, btn_h))

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
        # Titre centré avec contour blanc
        blit_text_with_outline_center(
            surface, "Classements", self.title_font, DARK_GREEN, WHITE,
            (self.screen_rect.centerx, int(self.screen_rect.height * 0.08)), thickness=3
        )

        # Boutons période (actif en vert plus clair)
        for b in (self.daily_btn, self.weekly_btn, self.monthly_btn):
            active = (
                (self.current_period == "daily"   and b.text == "Jour") or
                (self.current_period == "weekly"  and b.text == "Semaine") or
                (self.current_period == "monthly" and b.text == "Mois")
            )
            color = (100,150,60) if active else DARK_GREEN
            pygame.draw.rect(surface, color, b.rect, border_radius=b.radius)
            b.draw(surface)

        # Tableau
        y = int(self.screen_rect.height * 0.30)
        line_gap = int(clamp(self.screen_rect.height * 0.055, 32, 72))
        for i, (score, username, created_at) in enumerate(self.rows, 1):
            line = f"{i:>2}. {username:<15} — {score} pts"
            surf = self.ui_font.render(line, True, DARK_GREEN)
            surface.blit(surf, surf.get_rect(midtop=(self.screen_rect.centerx, y)))
            y += line_gap

        if not self.rows:
            empty = self.ui_font.render("Aucun score enregistré.", True, DARK_GREEN)
            surface.blit(empty, empty.get_rect(center=self.screen_rect.center))

        self.back_btn.draw(surface)

# =========================
#   Instanciation & Layout
# =========================
compute_layout_for_window(screen_rect.w, screen_rect.h)
rescale_assets()
game = Game()
menu_screen = MenuScreen(screen_rect, title_font, ui_font)
leader_screen = LeaderboardScreen(screen_rect, title_font, ui_font)

SNAKE_UPDATE = pygame.USEREVENT
pygame.time.set_timer(SNAKE_UPDATE, 200)

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
            menu_screen.relayout(screen_rect)
            leader_screen.relayout(screen_rect)

        if app_state == "MENU":
            action, payload = menu_screen.handle_event(event)
            if action == "START":
                pseudo = (payload or "").strip()
                if not pseudo:
                    menu_screen.message = "Veuillez entrer un pseudo."
                else:
                    # Attrape les erreurs de validation levées par db.get_or_create_player
                    try:
                        current_player_name = pseudo
                        current_player_id = db.get_or_create_player(pseudo)
                    except ValueError as e:
                        menu_screen.message = str(e)  # ex: "Username must be 3..20 chars ..."
                    else:
                        game.state = "PLAYING"
                        app_state = "PLAYING"
                        menu_screen.message = ""
            elif action == "LEADERBOARD":
                leader_screen.load_rows()
                app_state = "LEADERBOARD"

        elif app_state == "LEADERBOARD":
            if leader_screen.handle_event(event) == "BACK":
                app_state = "MENU"

        elif app_state == "PLAYING":
            if event.type == SNAKE_UPDATE:
                game.update()
            if event.type == pygame.KEYDOWN:
                if game.state == "STOPPED": game.state = "PLAYING"
                if event.key == pygame.K_UP    and game.snake.direction != Vector2(0, 1):  game.snake.direction = Vector2(0, -1)
                if event.key == pygame.K_DOWN  and game.snake.direction != Vector2(0,-1): game.snake.direction = Vector2(0, 1)
                if event.key == pygame.K_LEFT  and game.snake.direction != Vector2(1, 0):  game.snake.direction = Vector2(-1, 0)
                if event.key == pygame.K_RIGHT and game.snake.direction != Vector2(-1,0): game.snake.direction = Vector2(1, 0)

    # --- DRAW ---
    screen.fill(GREEN)

    # Fond jungle
    if app_state in ("MENU", "LEADERBOARD"):
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
        # cadre du board
        pygame.draw.rect(
            screen, DARK_GREEN,
            (offset_x - 5, offset_y - 5, board_size + 10, board_size + 10),
            5
        )
        game.draw()

        # HUD (titre + score) avec contour blanc, hors de la grille
        hud_y = max(10, int(offset_y * 0.6))
        blit_text_with_outline_topleft(
            screen, "Snake Game", title_font, DARK_GREEN, WHITE,
            offset_x - 5, hud_y, thickness=3
        )
        blit_text_with_outline_topright(
            screen, str(game.score), score_font, DARK_GREEN, WHITE,
            screen_rect.w - offset_x, hud_y, thickness=3
        )

    pygame.display.update()
