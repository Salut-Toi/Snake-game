import pygame, sys, random
from pygame.math import Vector2
import os

pygame.init()

GREEN = (173, 204, 96)
DARK_GREEN = (43, 51, 24)

cell_size = 30
number_of_cells = 25

# --- fenêtre d'abord (important pour convert_alpha) ---
screen = pygame.display.set_mode((cell_size * number_of_cells, 750))
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
    def __init__(self):
        self.position = self.generate_random_position()

    def draw(self):
        # conversion grille -> pixels
        x = int(self.position.x) * cell_size
        y = int(self.position.y) * cell_size
        screen.blit(food_surface, (x, y))

    def generate_random_position(self):
        x = random.randint(0, number_of_cells - 1)
        y = random.randint(0, number_of_cells - 1)
        position = Vector2(x, y)
        return position
    
class Snake:
    def __init__(self):
        self.body = [Vector2(6, 9), Vector2(5, 9), Vector2(4, 9)]
        
    def draw(self):
        for segment in self.body:
            segment_rect = (segment.x * cell_size, segment.y * cell_size, cell_size, cell_size)
            pygame.draw.rect(screen, DARK_GREEN, segment_rect, 0, 6)
food = Food()
Snake = Snake()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    screen.fill(GREEN)
    food.draw()
    Snake.draw()
    pygame.display.update()
    clock.tick(60)
