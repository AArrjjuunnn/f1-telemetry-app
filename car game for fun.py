import pygame
import random
import sys

# Initialize Pygame
pygame.init()

# Screen dimensions
WIDTH, HEIGHT = 400, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Car Game")

# Colors
GRAY = (119, 119, 119)
WHITE = (255, 255, 255)
RED = (200, 0, 0)
CAR_COLOR = (0, 0, 200)

# Car settings
CAR_WIDTH = 50
CAR_HEIGHT = 80
player_x = WIDTH // 2 - CAR_WIDTH // 2
player_y = HEIGHT - CAR_HEIGHT - 10
player_speed = 5

# Obstacle settings
obstacle_width = 50
obstacle_height = 80
obstacle_x = random.randint(0, WIDTH - obstacle_width)
obstacle_y = -600
obstacle_speed = 5

clock = pygame.time.Clock()

# Main game loop
while True:
    screen.fill(GRAY)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    # Player movement
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT] and player_x > 0:
        player_x -= player_speed
    if keys[pygame.K_RIGHT] and player_x < WIDTH - CAR_WIDTH:
        player_x += player_speed

    # Obstacle movement
    obstacle_y += obstacle_speed
    if obstacle_y > HEIGHT:
        obstacle_y = -600
        obstacle_x = random.randint(0, WIDTH - obstacle_width)

    # Draw cars
    player_rect = pygame.Rect(player_x, player_y, CAR_WIDTH, CAR_HEIGHT)
    obstacle_rect = pygame.Rect(obstacle_x, obstacle_y, obstacle_width, obstacle_height)

    pygame.draw.rect(screen, CAR_COLOR, player_rect)  # Player
    pygame.draw.rect(screen, RED, obstacle_rect)  # Obstacle

    # Collision detection
    if player_rect.colliderect(obstacle_rect):
        print("Game Over")
        pygame.quit()
        sys.exit()

    pygame.display.update()
    clock.tick(60)
