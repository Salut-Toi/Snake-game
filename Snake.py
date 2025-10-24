import pygame, sys, random
from pygame.math import Vector2
import os

pygame.init()

title_font = pygame.font.Font(None, 60)
score_font = pygame.font.Font(None, 40)

GREEN = (173, 204, 96)
DARK_GREEN = (43, 51, 24)

cell_size = 30
number_of_cells = 25

offset = 75  # espace pour le score en haut

# --- fenêtre d'abord (important pour convert_alpha) ---
screen = pygame.display.set_mode((2*offset + cell_size * number_of_cells, 2*offset + cell_size * number_of_cells))
pygame.display.set_caption("Snake Game")
clock = pygame.time.Clock()

# --- chargement + transparence + redimensionnement ---
# chemin robuste (facultatif)
base_path = os.path.dirname(__file__)
apple_path = os.path.join(base_path, "images", "apple.png")

# charge l'image avec alpha (après set_mode)
apple_raw = pygame.image.load(apple_path).convert_alpha()

# si ton png a un fond uni (vert), le rendre transparent :
bg = apple_raw.get_at((0, 0))          # prend la couleur du coin haut-gauche (le vert de fond)
apple_raw.set_colorkey(bg)             # ce vert deviendra transparent

# redimensionne à la taille d'une cellule (scale pour garder le pixel art net)
food_surface = pygame.transform.scale(apple_raw, (cell_size, cell_size))

class Food:
    def __init__(self, snake_body):
        self.position = self.generate_random_position(snake_body)

    def draw(self):
        # conversion grille -> pixels
        x = int(self.position.x * cell_size + offset)
        y = int(self.position.y * cell_size + offset)
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
            segment_rect = (offset + segment.x * cell_size, offset + segment.y * cell_size, cell_size, cell_size)
            pygame.draw.rect(screen, DARK_GREEN, segment_rect, 0, 6)

    def update(self):
        self.body.insert(0, self.body[0] + self.direction)
        if self.new_block == True:
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
        self.state = "PLAYING"
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
        if self.snake.body[0].x == number_of_cells or self.snake.body[0].x == -1:
            self.game_over()
        if self.snake.body[0].y == number_of_cells or self.snake.body[0].y == -1:
            self.game_over()

    def game_over(self):
        self.snake.reset()
        self.food.position = self.food.generate_random_position(self.snake.body)
        self.state = "STOPPED"
        self.score = 0

    def check_self_collision(self):
        headless_body = self.snake.body[1:]
        if self.snake.body[0] in headless_body:
            self.game_over()

game = Game()
SNAKE_UPDATE = pygame.USEREVENT
pygame.time.set_timer(SNAKE_UPDATE, 200)

while True:
    for event in pygame.event.get():
        if event.type == SNAKE_UPDATE:
            game.update()
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if game.state == "STOPPED":
                game.state = "PLAYING"
            if event.key == pygame.K_UP and game.snake.direction != Vector2(0, 1):
                game.snake.direction = Vector2(0, -1)
            if event.key == pygame.K_DOWN and game.snake.direction != Vector2(0, -1):
                game.snake.direction = Vector2(0, 1)
            if event.key == pygame.K_LEFT and game.snake.direction != Vector2(-1, 0) and game.snake.direction != Vector2(1, 0):
                game.snake.direction = Vector2(-1, 0)
            if event.key == pygame.K_RIGHT and game.snake.direction != Vector2(1, 0) and game.snake.direction != Vector2(-1, 0):
                game.snake.direction = Vector2(1, 0)

    screen.fill(GREEN)
    pygame.draw.rect(screen, DARK_GREEN, (offset-5, offset-5, cell_size*number_of_cells+10, cell_size*number_of_cells+10), 5)
    game.draw()
    title_surface = title_font.render("Snake Game", True, DARK_GREEN)
    score_surface = score_font.render(str (game.score), True, DARK_GREEN)
    screen.blit(title_surface, (offset-5, 20))
    screen_width = cell_size * number_of_cells + offset * 2
    score_rect = score_surface.get_rect(topright=(screen_width - offset, 20))
    screen.blit(score_surface, score_rect)
    pygame.display.update()
    clock.tick(60)
