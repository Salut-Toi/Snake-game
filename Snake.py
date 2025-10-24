import pygame, sys, random, os
from pygame.math import Vector2
import db

# === DB ===
db.init_db()

# === Joueur courant ===
current_player_id = None
current_player_name = None

pygame.init()

# === Couleurs ===
GREEN = (173, 204, 96)
DARK_GREEN = (43, 51, 24)

# === Paramètres grille de base ===
number_of_cells = 25           # 25x25
offset_cells = 2.5             # marge autour du plateau (en "cellules")
cell_size = 30                 # taille initiale d'une cellule (variera avec la fenêtre)
offset_px = int(offset_cells * cell_size)

# === Fenêtre (créée AVANT le chargement des images) ===
def compute_initial_window():
    side = int(round((number_of_cells + 2 * offset_cells) * cell_size))
    return side, side

BASE_W, BASE_H = compute_initial_window()  # sert de référence pour le scale de l'UI
screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
pygame.display.set_caption("Snake Game")
clock = pygame.time.Clock()
screen_rect = screen.get_rect()

# === Chargement images APRÈS ouverture de la fenêtre ===
base_path = os.path.dirname(__file__)

# Pomme
apple_path = os.path.join(base_path, "images", "apple.png")
apple_raw = pygame.image.load(apple_path).convert_alpha()
bg = apple_raw.get_at((0, 0))
apple_raw.set_colorkey(bg)

# Logo menu (optionnel)
logo_path = r"C:\Users\kyman\Snake-game\images\snake.png"
logo_raw = pygame.image.load(logo_path).convert_alpha() if os.path.exists(logo_path) else None

# Bordure décorative
border_path = os.path.join(base_path, "images", "border.png")
border_raw = pygame.image.load(border_path).convert_alpha() if os.path.exists(border_path) else None

# Si ta bordure source fait 1024x1024 et que la "fenêtre" intérieure libre est décalée de ~128 px
# depuis chaque bord, mets 128 ici. Ajuste si nécessaire pour coller pile à ton asset.
BORDER_INSET_SRC = 128  # <-- ajuste ce chiffre si le feuillage est plus/moins épais dans ton PNG

# === Polices (seront régénérées selon le scale) ===
def clamp(v, lo, hi): return max(lo, min(hi, v))

def make_fonts(scale: float):
    title_size = int(clamp(72 * scale, 36, 120))
    score_size = int(clamp(40 * scale, 24, 72))
    ui_size    = int(clamp(38 * scale, 22, 56))
    return (
        pygame.font.Font(None, title_size),
        pygame.font.Font(None, score_size),
        pygame.font.Font(None, ui_size),
    )

# init polices
title_font, score_font, ui_font = make_fonts(1.0)

# === Surfaces dépendantes de la taille ===
food_surface = None
logo_surface = None

def rescale_assets():
    """Redimensionne les surfaces selon la taille de la cellule."""
    global food_surface, logo_surface
    food_surface = pygame.transform.smoothscale(apple_raw, (cell_size, cell_size))
    if logo_raw:
        logo_side = int(clamp(cell_size * 5, 80, 260))  # logo ~5 cellules
        logo_surface = pygame.transform.smoothscale(logo_raw, (logo_side, logo_side))
    else:
        logo_surface = None

# --- Calcul du placement/zoom de la bordure ---
def compute_border_target_rect():
    """Calcule le rectangle destination de la bordure pour que sa 'fenêtre' interne
       corresponde exactement au plateau (board)."""
    if not border_raw:
        return None
    W, H = border_raw.get_size()
    inset = BORDER_INSET_SRC
    board_size = cell_size * number_of_cells
    # On veut: (W - 2*inset) * s == board_size  => s:
    s_x = board_size / (W - 2*inset)
    s_y = board_size / (H - 2*inset)
    s = min(s_x, s_y)  # par sécurité si pas parfaitement carré
    dest_w = int(W * s)
    dest_h = int(H * s)
    x = int(offset_px - inset * s)
    y = int(offset_px - inset * s)
    return pygame.Rect(x, y, dest_w, dest_h)

def screen_fit_rect():
    return pygame.Rect(0, 0, screen_rect.width, screen_rect.height)

def lerp(a, b, t): return a + (b - a) * t
def lerp_rect(r1, r2, t):
    return pygame.Rect(int(lerp(r1.x, r2.x, t)),
                       int(lerp(r1.y, r2.y, t)),
                       int(lerp(r1.w, r2.w, t)),
                       int(lerp(r1.h, r2.h, t)))

border_current_rect = screen_fit_rect()
border_target_rect  = compute_border_target_rect()

# Animation
ZOOM_DURATION_MS = 650
zoom_start_ms = None

def start_border_zoom():
    global app_state, zoom_start_ms, border_current_rect, border_target_rect
    zoom_start_ms = pygame.time.get_ticks()
    border_current_rect = screen_fit_rect()
    border_target_rect  = compute_border_target_rect()
    app_state = "ZOOMING"

def draw_border_at_rect(rect: pygame.Rect):
    if not border_raw or rect is None:
        return
    scaled = pygame.transform.smoothscale(border_raw, (rect.w, rect.h))
    screen.blit(scaled, rect.topleft)

def update_scaling_for_window(w, h):
    """Recalcule cell_size/offset_px selon la taille de la fenêtre et rescale l'UI + bordure."""
    global cell_size, offset_px, title_font, score_font, ui_font, border_target_rect, border_current_rect
    denom = (number_of_cells + 2 * offset_cells)
    new_cell = max(12, int(min(w, h) / denom))
    if new_cell != cell_size:
        cell_size = new_cell
        offset_px = int(round(offset_cells * cell_size))
        rescale_assets()
    # scale UI par rapport à la taille de fenêtre actuelle vs base
    scale_ui = min(w / BASE_W, h / BASE_H)
    title_font, score_font, ui_font = make_fonts(scale_ui)
    # recalcul de la cible bordure
    border_target_rect = compute_border_target_rect()
    # si on est en PLAYING, caler le rect courant sur la cible
    if app_state == "PLAYING":
        border_current_rect = border_target_rect.copy() if border_target_rect else None
    else:
        border_current_rect = screen_fit_rect()

# premières surfaces
rescale_assets()

# =========================
#        UI Widgets
# =========================
class Button:
    def __init__(self, rect, text, font, bg_color, text_color,
                 hover_color=None, radius=10):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.bg_color = bg_color
        self.text_color = text_color
        self.hover_color = hover_color or bg_color
        self.radius = radius

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def set_font(self, font):
        self.font = font

    def draw(self, surface):
        mouse_pos = pygame.mouse.get_pos()
        color = self.hover_color if self.rect.collidepoint(mouse_pos) else self.bg_color
        pygame.draw.rect(surface, color, self.rect, border_radius=self.radius)
        label = self.font.render(self.text, True, self.text_color)
        surface.blit(label, label.get_rect(center=self.rect.center))

    def is_clicked(self, event):
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )

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

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def set_font(self, font):
        self.font = font

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

    def update(self, dt_ms):
        self.cursor_timer += dt_ms
        if self.cursor_timer > 500:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

    def draw(self, surface):
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=self.radius)
        pygame.draw.rect(surface, self.border_color, self.rect, width=2, border_radius=self.radius)
        if self.text:
            label = self.font.render(self.text, True, self.text_color)
        else:
            label = self.font.render(self.placeholder, True, (120, 120, 120))
        surface.blit(label, (self.rect.x + 10, self.rect.y + (self.rect.height - label.get_height()) // 2))
        if self.active and self.cursor_visible:
            cursor_x = self.rect.x + 10 + (self.font.size(self.text)[0] if self.text else 0)
            cursor_y = self.rect.y + 8
            pygame.draw.line(surface, self.text_color, (cursor_x, cursor_y),
                             (cursor_x, self.rect.bottom - 8), 2)

# =========================
#         Jeu
# =========================
class Food:
    def __init__(self, snake_body):
        self.position = self.generate_random_position(snake_body)

    def draw(self):
        x = int(self.position.x * cell_size + offset_px)
        y = int(self.position.y * cell_size + offset_px)
        screen.blit(food_surface, (x, y))

    def generate_random_cell(self):
        x = random.randint(0, number_of_cells - 1)
        y = random.randint(0, number_of_cells - 1)
        return Vector2(x, y)

    def generate_random_position(self, snake_body):
        position = self.generate_random_cell()
        while position in snake_body:
            position = self.generate_random_cell()
        return position

class Snake:
    def __init__(self):
        self.body = [Vector2(6, 9), Vector2(5, 9), Vector2(4, 9)]
        self.direction = Vector2(1, 0)
        self.new_block = False

    def draw(self):
        for segment in self.body:
            segment_rect = (
                offset_px + segment.x * cell_size,
                offset_px + segment.y * cell_size,
                cell_size, cell_size
            )
            pygame.draw.rect(screen, DARK_GREEN, segment_rect, 0, 6)

    def update(self):
        self.body.insert(0, self.body[0] + self.direction)
        if self.new_block:
            self.new_block = False
        else:
            self.body = self.body[:-1]

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
        if self.snake.body[0].x in (-1, number_of_cells) or self.snake.body[0].y in (-1, number_of_cells):
            self.game_over()

    def game_over(self):
        global current_player_id, app_state, border_current_rect, border_target_rect
        try:
            db.record_run(score=self.score, player_id=current_player_id)
        except Exception as e:
            print("DB error:", e)
        self.snake.reset()
        self.food.position = self.food.generate_random_position(self.snake.body)
        self.state = "STOPPED"
        self.score = 0
        # revenir au menu et remettre la bordure en "plein écran"
        border_current_rect = screen_fit_rect()
        border_target_rect  = compute_border_target_rect()
        app_state = "MENU"

    def check_self_collision(self):
        headless_body = self.snake.body[1:]
        if self.snake.body[0] in headless_body:
            self.game_over()

# =========================
#       Écrans UI
# =========================
class MenuScreen:
    def __init__(self, screen_rect, title_font, ui_font, DARK_GREEN, GREEN):
        self.DARK_GREEN = DARK_GREEN
        self.GREEN = GREEN
        self.title_font = title_font
        self.ui_font = ui_font
        self.screen_rect = screen_rect

        # Widgets (rects définis dans relayout)
        self.input = TextInput(pygame.Rect(0, 0, 10, 10), ui_font, DARK_GREEN, (240, 245, 230), DARK_GREEN)
        self.start_btn = Button(pygame.Rect(0, 0, 10, 10), "Démarrer", ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.leader_btn = Button(pygame.Rect(0, 0, 10, 10), "Leaderboard", ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.message = ""
        self.relayout(screen_rect)

    def relayout(self, screen_rect):
        self.screen_rect = screen_rect
        w, h = screen_rect.size
        input_w = int(clamp(w * 0.5, 320, 720))
        input_h = int(clamp(h * 0.06, 40, 90))
        center_y = int(h * 0.5)
        self.input.set_rect(pygame.Rect(screen_rect.centerx - input_w // 2, center_y, input_w, input_h))
        btn_w = int(clamp(w * 0.32, 220, 420))
        btn_h = int(clamp(h * 0.07, 50, 100))
        self.start_btn.set_rect(pygame.Rect(screen_rect.centerx - btn_w // 2, center_y + int(h*0.10), btn_w, btn_h))
        self.leader_btn.set_rect(pygame.Rect(screen_rect.centerx - btn_w // 2, center_y + int(h*0.20), btn_w, btn_h))

    def apply_fonts(self, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        self.input.set_font(ui_font)
        self.start_btn.set_font(ui_font)
        self.leader_btn.set_font(ui_font)

    def handle_event(self, event):
        submit = self.input.handle_event(event)
        if submit == "submit":
            return ("START", self.input.text.strip() or None)
        if self.start_btn.is_clicked(event):
            return ("START", self.input.text.strip() or None)
        if self.leader_btn.is_clicked(event):
            return ("LEADERBOARD", None)
        return (None, None)

    def update(self, dt_ms):
        self.input.update(dt_ms)

    def draw(self, surface):
        title_surf = self.title_font.render("Snake Game", True, self.DARK_GREEN)
        surface.blit(title_surf, title_surf.get_rect(midtop=(self.screen_rect.centerx, int(self.screen_rect.height * 0.12))))
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
    def __init__(self, screen_rect, title_font, ui_font, DARK_GREEN, GREEN):
        self.DARK_GREEN = DARK_GREEN
        self.GREEN = GREEN
        self.title_font = title_font
        self.ui_font = ui_font
        self.screen_rect = screen_rect
        self.rows = []
        self.back_btn = Button(pygame.Rect(0, 0, 10, 10), "Retour", ui_font, DARK_GREEN, (255,255,255), (60,72,35))
        self.relayout(screen_rect)

    def relayout(self, screen_rect):
        self.screen_rect = screen_rect
        w, h = screen_rect.size
        btn_w = int(clamp(w * 0.18, 160, 320))
        btn_h = int(clamp(h * 0.06, 44, 90))
        self.back_btn.set_rect(pygame.Rect(screen_rect.centerx - btn_w // 2, h - btn_h - int(h*0.05), btn_w, btn_h))

    def apply_fonts(self, title_font, ui_font):
        self.title_font = title_font
        self.ui_font = ui_font
        self.back_btn.set_font(ui_font)

    def load_rows(self):
        self.rows = db.top_scores(10)

    def handle_event(self, event):
        if self.back_btn.is_clicked(event):
            return "BACK"
        return None

    def draw(self, surface):
        title = self.title_font.render("Top 10 des Scores", True, self.DARK_GREEN)
        surface.blit(title, title.get_rect(midtop=(self.screen_rect.centerx, int(self.screen_rect.height * 0.10))))
        y = int(self.screen_rect.height * 0.22)
        line_gap = int(clamp(self.screen_rect.height * 0.055, 32, 72))
        for i, (score, username, created_at) in enumerate(self.rows, 1):
            line = f"{i:>2}. {username:<15} — {score} pts"
            surf = self.ui_font.render(line, True, self.DARK_GREEN)
            surface.blit(surf, surf.get_rect(midtop=(self.screen_rect.centerx, y)))
            y += line_gap
        if not self.rows:
            empty = self.ui_font.render("Aucun score enregistré.", True, self.DARK_GREEN)
            surface.blit(empty, empty.get_rect(center=self.screen_rect.center))
        self.back_btn.draw(surface)

# =========================
#     Instanciation
# =========================
game = Game()
menu_screen = MenuScreen(screen_rect, title_font, ui_font, DARK_GREEN, GREEN)
leader_screen = LeaderboardScreen(screen_rect, title_font, ui_font, DARK_GREEN, GREEN)
app_state = "MENU"

SNAKE_UPDATE = pygame.USEREVENT
pygame.time.set_timer(SNAKE_UPDATE, 200)

# =========================
#     Boucle principale
# =========================
while True:
    dt = clock.tick(60)
    now_ms = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            screen_rect = screen.get_rect()
            update_scaling_for_window(event.w, event.h)
            # Appliquer nouvelles polices aux écrans
            menu_screen.apply_fonts(title_font, ui_font)
            leader_screen.apply_fonts(title_font, ui_font)
            # Recalcule leurs layouts avec le nouveau screen_rect
            menu_screen.relayout(screen_rect)
            leader_screen.relayout(screen_rect)

        if app_state == "MENU":
            action, payload = menu_screen.handle_event(event)
            if action == "START":
                pseudo = (payload or "").strip()
                if not pseudo:
                    menu_screen.message = "Veuillez entrer un pseudo."
                else:
                    current_player_name = pseudo
                    current_player_id = db.get_or_create_player(pseudo)
                    # lance l'animation de zoom de la bordure
                    start_border_zoom()
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
                if game.state == "STOPPED":
                    game.state = "PLAYING"
                if event.key == pygame.K_UP and game.snake.direction != Vector2(0, 1):
                    game.snake.direction = Vector2(0, -1)
                if event.key == pygame.K_DOWN and game.snake.direction != Vector2(0, -1):
                    game.snake.direction = Vector2(0, 1)
                if event.key == pygame.K_LEFT and game.snake.direction != Vector2(1, 0):
                    game.snake.direction = Vector2(-1, 0)
                if event.key == pygame.K_RIGHT and game.snake.direction != Vector2(-1, 0):
                    game.snake.direction = Vector2(1, 0)

    # --- DRAW ---
    screen.fill(GREEN)

    # Dessin de la bordure selon l'état
    if border_raw:
        if app_state == "MENU":
            # plein écran sous le menu
            draw_border_at_rect(screen_fit_rect())
        elif app_state == "ZOOMING":
            # interpolation du zoom
            t = clamp((now_ms - zoom_start_ms) / ZOOM_DURATION_MS, 0.0, 1.0)
            if border_target_rect is None:
                border_target_rect = compute_border_target_rect()
            if border_current_rect is None:
                border_current_rect = screen_fit_rect()
            cur = lerp_rect(border_current_rect, border_target_rect, t)
            draw_border_at_rect(cur)
            # Dessine HUD (titre+score à 0) pour montrer qu'ils restent sur le feuillage
            title_surface = title_font.render("Snake Game", True, DARK_GREEN)
            screen.blit(title_surface, (offset_px - 5, int(screen_rect.height * 0.03)))
            score_surface = score_font.render("0", True, DARK_GREEN)
            screen.blit(score_surface, score_surface.get_rect(
                topright=(screen_rect.width - offset_px, int(screen_rect.height * 0.03))
            ))
            # quand l'animation est finie -> PLAYING
            if t >= 1.0:
                border_current_rect = border_target_rect.copy()
                app_state = "PLAYING"
        elif app_state == "PLAYING":
            # Bordure calée pour que le feuillage reste dans l'offset
            if border_target_rect is None:
                border_target_rect = compute_border_target_rect()
            draw_border_at_rect(border_target_rect)

    # UI/Menu/Leaderboard/Jeu
    if app_state == "MENU":
        menu_screen.update(dt)
        menu_screen.draw(screen)

    elif app_state == "LEADERBOARD":
        leader_screen.draw(screen)

    elif app_state in ("ZOOMING", "PLAYING"):
        board_size = cell_size * number_of_cells
        # cadre du plateau par-dessus la bordure
        pygame.draw.rect(
            screen, DARK_GREEN,
            (offset_px - 5, offset_px - 5, board_size + 10, board_size + 10),
            5
        )
        if app_state == "PLAYING":
            game.draw()

        # HUD au-dessus de tout
        title_surface = title_font.render("Snake Game", True, DARK_GREEN)
        screen.blit(title_surface, (offset_px - 5, int(screen_rect.height * 0.03)))
        score_text = str(game.score if app_state == "PLAYING" else 0)
        score_surface = score_font.render(score_text, True, DARK_GREEN)
        screen.blit(score_surface, score_surface.get_rect(
            topright=(screen_rect.width - offset_px, int(screen_rect.height * 0.03))
        ))

    pygame.display.update()
