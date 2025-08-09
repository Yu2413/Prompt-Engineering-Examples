import math
import random
import sys
from dataclasses import dataclass

import pygame
from pygame import Vector2

"""
Air Combat — a minimal top‑down arcade shooter built with pygame.

Run:
    pip install pygame==2.*
    python air_combat.py

Controls:
    Arrow keys / WASD  Move
    Space              Fire
    Left Shift         Slow/precision move
    P                  Pause / Resume
    ESC                Quit

Gameplay:
    - Survive waves of enemies and earn score.
    - Collect power‑ups for shields, rapid fire, and heal.
    - Every 45–60 seconds (scaled by performance) a boss spawns.

This file is completely asset‑free: ships, bullets, and effects are drawn
with simple shapes. Tweak GAME_* constants to rebalance.
"""

# --------------------------- Config ------------------------------------ #
WIDTH, HEIGHT = 900, 1200
FPS = 60
GAME_TITLE = "Air Combat (pygame)"

# Player
PLAYER_SPEED = 480
PLAYER_SPEED_SLOW = 260
PLAYER_RADIUS = 22
PLAYER_FIRE_COOLDOWN = 0.16
PLAYER_MAX_HP = 5
PLAYER_SHOT_SPEED = 900
PLAYER_SHOT_DMG = 1

# Enemies
ENEMY_MIN_SPEED, ENEMY_MAX_SPEED = 110, 220
ENEMY_SPAWN_EVERY = 0.55  # seconds
ENEMY_RADIUS = 18
ENEMY_HP = 2

# Boss
BOSS_HP = 120
BOSS_SPEED = 120
BOSS_RADIUS = 80
BOSS_COOLDOWN = 0.9

# Powerups
POWERUP_RADIUS = 16
POWERUP_DROP_CHANCE = 0.10
POWERUP_LIFETIME = 10.0

# Misc
STAR_COUNT = 120
SHAKE_DECAY = 0.9

# Colors
WHITE = (240, 240, 240)
BLACK = (10, 10, 14)
GRAY = (120, 130, 140)
YELLOW = (255, 210, 0)
ORANGE = (255, 140, 0)
RED = (220, 60, 60)
BLUE = (90, 190, 255)
CYAN = (80, 230, 230)
GREEN = (80, 220, 120)
PURPLE = (190, 120, 255)

# --------------------------- Helpers ----------------------------------- #

@dataclass
class Timer:
    t: float = 0.0
    def update(self, dt):
        self.t = max(0.0, self.t - dt)
    def ready(self):
        return self.t <= 0.0
    def set(self, sec):
        self.t = sec

class CameraShake:
    def __init__(self):
        self.power = 0.0
    def bump(self, amt):
        self.power = min(30.0, self.power + amt)
    def update(self):
        self.power *= SHAKE_DECAY
    def offset(self):
        if self.power < 0.5:
            return Vector2()
        return Vector2(random.uniform(-self.power, self.power),
                       random.uniform(-self.power, self.power))

# --------------------------- Entities ---------------------------------- #

class Bullet(pygame.sprite.Sprite):
    def __init__(self, pos, vel, friendly=True, dmg=1, color=YELLOW, radius=4):
        super().__init__()
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.friendly = friendly
        self.dmg = dmg
        self.color = color
        self.radius = radius
        self.rect = pygame.Rect(0, 0, radius * 2, radius * 2)
    def update(self, dt):
        self.pos += self.vel * dt
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if self.pos.y < -40 or self.pos.y > HEIGHT + 40 or self.pos.x < -40 or self.pos.x > WIDTH + 40:
            self.kill()
    def draw(self, surf):
        pygame.draw.circle(surf, self.color, self.rect.center, self.radius)

class Explosion(pygame.sprite.Sprite):
    def __init__(self, pos, color=ORANGE, duration=0.35):
        super().__init__()
        self.pos = Vector2(pos)
        self.timer = duration
        self.color = color
        self.max_r = 36
        self.rect = pygame.Rect(0, 0, self.max_r * 2, self.max_r * 2)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.kill()
    def draw(self, surf):
        p = max(0.0, self.timer) / 0.35
        r = int(self.max_r * (1 - p))
        if r > 0:
            pygame.draw.circle(surf, self.color, self.rect.center, r)
            pygame.draw.circle(surf, YELLOW, self.rect.center, max(1, r // 2), 2)

class FloatingText(pygame.sprite.Sprite):
    def __init__(self, pos, text, color=WHITE):
        super().__init__()
        self.pos = Vector2(pos)
        self.text = text
        self.color = color
        self.timer = 1.0
        self.v = Vector2(0, -50)
    def update(self, dt):
        self.timer -= dt
        self.pos += self.v * dt
        if self.timer <= 0:
            self.kill()
    def draw(self, surf, font):
        img = font.render(self.text, True, self.color)
        surf.blit(img, img.get_rect(center=(int(self.pos.x), int(self.pos.y))))

class PowerUp(pygame.sprite.Sprite):
    TYPES = ("shield", "rapid", "heal")
    COLORS = {"shield": CYAN, "rapid": PURPLE, "heal": GREEN}
    def __init__(self, pos):
        super().__init__()
        self.kind = random.choice(PowerUp.TYPES)
        self.color = PowerUp.COLORS[self.kind]
        self.pos = Vector2(pos)
        self.timer = POWERUP_LIFETIME
        self.rect = pygame.Rect(0, 0, POWERUP_RADIUS * 2, POWERUP_RADIUS * 2)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        self.vel = Vector2(random.uniform(-40, 40), random.uniform(40, 120))
    def update(self, dt):
        self.timer -= dt
        self.pos += self.vel * dt
        self.vel.y = min(self.vel.y + 50 * dt, 160)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if self.timer <= 0 or self.pos.y > HEIGHT + 50:
            self.kill()
    def draw(self, surf):
        pygame.draw.circle(surf, self.color, self.rect.center, POWERUP_RADIUS)
        pygame.draw.circle(surf, WHITE, self.rect.center, POWERUP_RADIUS, 2)

class Enemy(pygame.sprite.Sprite):
    def __init__(self, pos, hp=ENEMY_HP):
        super().__init__()
        self.pos = Vector2(pos)
        self.hp = hp
        self.speed = random.uniform(ENEMY_MIN_SPEED, ENEMY_MAX_SPEED)
        self.rect = pygame.Rect(0, 0, ENEMY_RADIUS * 2, ENEMY_RADIUS * 2)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        self.shoot_t = Timer()
        self.shoot_t.set(random.uniform(0.8, 1.6))
    def update(self, dt, bullets, effects):
        self.pos.y += self.speed * dt
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        self.shoot_t.update(dt)
        if self.shoot_t.ready():
            self.shoot_t.set(random.uniform(1.1, 2.0))
            vel = Vector2(0, 320)
            bullets.add(Bullet(self.pos + Vector2(0, ENEMY_RADIUS), vel, friendly=False, dmg=1, color=RED, radius=5))
        if self.pos.y > HEIGHT + 40:
            self.kill()
    def draw(self, surf):
        x, y = self.rect.center
        pygame.draw.polygon(surf, RED, [(x, y-ENEMY_RADIUS), (x-ENEMY_RADIUS, y+ENEMY_RADIUS), (x+ENEMY_RADIUS, y+ENEMY_RADIUS)])
        # health bar
        hp_ratio = max(0.0, min(1.0, self.hp / ENEMY_HP))
        pygame.draw.rect(surf, RED, (x-ENEMY_RADIUS, y-ENEMY_RADIUS-8, ENEMY_RADIUS*2, 4), 1)
        pygame.draw.rect(surf, RED, (x-ENEMY_RADIUS+1, y-ENEMY_RADIUS-7, int((ENEMY_RADIUS*2-2)*hp_ratio), 2))

class Boss(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.pos = Vector2(WIDTH/2, -120)
        self.rect = pygame.Rect(0, 0, BOSS_RADIUS*2, BOSS_RADIUS*2)
        self.hp = BOSS_HP
        self.state = "enter"
        self.cool = Timer(); self.cool.set(BOSS_COOLDOWN)
        self.target_x = WIDTH/2
    def update(self, dt, bullets, effects):
        if self.state == "enter":
            self.pos.y += 100 * dt
            if self.pos.y >= 200:
                self.state = "fight"
        elif self.state == "fight":
            # sway horizontally towards target
            if abs(self.pos.x - self.target_x) < 10:
                self.target_x = random.uniform(120, WIDTH-120)
            dx = math.copysign(1, self.target_x - self.pos.x)
            self.pos.x += dx * BOSS_SPEED * dt
            self.cool.update(dt)
            if self.cool.ready():
                self.cool.set(BOSS_COOLDOWN)
                # radial burst
                for i in range(14):
                    ang = i * (math.tau/14) + random.uniform(-0.05,0.05)
                    vel = Vector2(math.cos(ang), math.sin(ang)) * 260
                    bullets.add(Bullet(self.pos, vel, friendly=False, dmg=1, color=ORANGE, radius=6))
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if self.hp <= 0:
            self.kill()
            for _ in range(8):
                effects.add(Explosion(self.pos + Vector2(random.uniform(-60,60), random.uniform(-40,40))))
    def draw(self, surf):
        x, y = self.rect.center
        pygame.draw.circle(surf, PURPLE, (x, y), BOSS_RADIUS)
        pygame.draw.rect(surf, WHITE, (150, 40, WIDTH-300, 20), 2)
        ratio = max(0.0, min(1.0, self.hp / BOSS_HP))
        pygame.draw.rect(surf, PURPLE, (152, 42, int((WIDTH-304) * ratio), 16))

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.pos = Vector2(WIDTH/2, HEIGHT-140)
        self.vel = Vector2()
        self.rect = pygame.Rect(0,0, PLAYER_RADIUS*2, PLAYER_RADIUS*2)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        self.hp = PLAYER_MAX_HP
        self.invuln = 0.0
        self.fire_t = Timer()
        self.rapid_timer = 0.0
        self.shield_timer = 0.0
        self.score = 0
    def update(self, dt, pressed, bullets):
        speed = PLAYER_SPEED_SLOW if pressed[pygame.K_LSHIFT] or pressed[pygame.K_RSHIFT] else PLAYER_SPEED
        self.vel.xy = 0,0
        if pressed[pygame.K_LEFT] or pressed[pygame.K_a]:
            self.vel.x -= 1
        if pressed[pygame.K_RIGHT] or pressed[pygame.K_d]:
            self.vel.x += 1
        if pressed[pygame.K_UP] or pressed[pygame.K_w]:
            self.vel.y -= 1
        if pressed[pygame.K_DOWN] or pressed[pygame.K_s]:
            self.vel.y += 1
        if self.vel.length_squared() > 0:
            self.vel = self.vel.normalize() * speed
        self.pos += self.vel * dt
        self.pos.x = max(40, min(WIDTH-40, self.pos.x))
        self.pos.y = max(150, min(HEIGHT-40, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        self.fire_t.update(dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.rapid_timer = max(0.0, self.rapid_timer - dt)
        self.shield_timer = max(0.0, self.shield_timer - dt)
    def try_fire(self, bullets):
        if not self.fire_t.ready():
            return
        cd = PLAYER_FIRE_COOLDOWN * (0.45 if self.rapid_timer > 0 else 1.0)
        self.fire_t.set(cd)
        # triple shot with slight spread
        for dx in (-14, 0, 14):
            vel = Vector2(dx * 8, -PLAYER_SHOT_SPEED)
            bullets.add(Bullet(self.pos + Vector2(dx, -PLAYER_RADIUS), vel, friendly=True, dmg=PLAYER_SHOT_DMG, color=YELLOW, radius=5))
    def draw(self, surf):
        x, y = self.rect.center
        body = [(x, y-PLAYER_RADIUS), (x-PLAYER_RADIUS, y+PLAYER_RADIUS), (x+PLAYER_RADIUS, y+PLAYER_RADIUS)]
        pygame.draw.polygon(surf, BLUE, body)
        if self.shield_timer > 0:
            rr = PLAYER_RADIUS + 8 + int(3*math.sin(pygame.time.get_ticks()*0.01))
            pygame.draw.circle(surf, CYAN, (x, y), rr, 2)
        # HP pips
        for i in range(PLAYER_MAX_HP):
            c = GREEN if i < self.hp else GRAY
            pygame.draw.rect(surf, c, (20 + i*26, HEIGHT-34, 22, 14), 0, 4)

# --------------------------- Game -------------------------------------- #

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(GAME_TITLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("consolas", 18)
        self.font_big = pygame.font.SysFont("consolas", 36, bold=True)

        self.reset()

    def reset(self):
        self.player = Player()
        self.all_bullets = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.effects = pygame.sprite.Group()
        self.floaters = pygame.sprite.Group()
        self.boss = pygame.sprite.GroupSingle()

        self.spawn_t = Timer(); self.spawn_t.set(1.0)
        self.time = 0.0
        self.running = True
        self.paused = False
        self.game_over = False
        self.shake = CameraShake()

        # star field
        self.stars = [Vector2(random.randrange(0, WIDTH), random.randrange(0, HEIGHT)) for _ in range(STAR_COUNT)]
        self.star_speed = [random.uniform(60, 200) for _ in range(STAR_COUNT)]

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.events()
            if not self.paused:
                self.update(dt)
            self.draw()
        pygame.quit()

    # -------------------- Systems -------------------- #
    def events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False
                elif e.key == pygame.K_p:
                    if not self.game_over:
                        self.paused = not self.paused
                elif e.key == pygame.K_SPACE and not self.game_over:
                    self.player.try_fire(self.all_bullets)
            elif e.type == pygame.MOUSEBUTTONDOWN and not self.game_over:
                if e.button == 1:
                    self.player.try_fire(self.all_bullets)

    def update(self, dt):
        if self.game_over:
            return
        pressed = pygame.key.get_pressed()
        self.player.update(dt, pressed, self.all_bullets)

        # Hold space to auto-fire
        if (pressed[pygame.K_SPACE] or pygame.mouse.get_pressed()[0]):
            self.player.try_fire(self.all_bullets)

        # update timers, starfield, shake
        self.time += dt
        self.spawn_t.update(dt)
        self.shake.update()
        for i, s in enumerate(self.stars):
            s.y += self.star_speed[i] * dt
            if s.y > HEIGHT:
                s.x = random.randrange(0, WIDTH)
                s.y = -5

        # spawn enemies
        if self.spawn_t.ready():
            self.spawn_t.set(max(0.25, ENEMY_SPAWN_EVERY - min(0.3, self.time/120)))
            x = random.randrange(40, WIDTH-40)
            self.enemies.add(Enemy((x, -40)))

        # boss spawn logic
        if self.time > 50 and self.boss.sprite is None:
            if self.player.score > 400 or self.time > 65:
                self.boss.add(Boss())

        # update groups
        for b in list(self.all_bullets):
            b.update(dt)
            if not b.friendly:
                self.enemy_bullets.add(b)
                self.all_bullets.remove(b)
        for b in list(self.enemy_bullets):
            b.update(dt)
        for e in list(self.enemies):
            e.update(dt, self.enemy_bullets, self.effects)
        for p in list(self.powerups):
            p.update(dt)
        for fx in list(self.effects):
            fx.update(dt)
        for ft in list(self.floaters):
            ft.update(dt)
        if self.boss.sprite:
            self.boss.sprite.update(dt, self.enemy_bullets, self.effects)

        # collisions: player bullets vs enemies/boss
        for b in [bb for bb in self.all_bullets if bb.friendly]:
            hit_list = [e for e in self.enemies if e.rect.collidepoint(b.rect.center)]
            if self.boss.sprite and self.boss.sprite.rect.collidepoint(b.rect.center):
                self.boss.sprite.hp -= b.dmg
                self.effects.add(Explosion(b.pos, color=YELLOW, duration=0.2))
                self.player.score += 2
                self.shake.bump(1.2)
                b.kill(); continue
            if hit_list:
                for e in hit_list:
                    e.hp -= b.dmg
                    self.effects.add(Explosion(b.pos, duration=0.2))
                    if e.hp <= 0:
                        e.kill()
                        self.player.score += 10
                        self.floaters.add(FloatingText(e.pos, "+10", YELLOW))
                        self.shake.bump(5)
                        if random.random() < POWERUP_DROP_CHANCE:
                            self.powerups.add(PowerUp(e.pos))
                b.kill()

        # enemy bullets vs player
        if self.player.invuln <= 0:
            for eb in [bb for bb in self.enemy_bullets]:
                if self.player.rect.collidepoint(eb.rect.center):
                    took = 0
                    if self.player.shield_timer > 0:
                        # consume shield time instead of HP
                        self.player.shield_timer = max(0.0, self.player.shield_timer - 0.35)
                    else:
                        self.player.hp -= 1; took = 1
                    self.effects.add(Explosion(eb.pos, color=RED, duration=0.25))
                    self.shake.bump(7 if took else 3)
                    self.player.invuln = 0.5
                    eb.kill()
                    break

        # enemies vs player (ramming)
        for e in [ee for ee in self.enemies if self.player.rect.colliderect(ee.rect)]:
            e.kill()
            if self.player.shield_timer > 0:
                self.player.shield_timer = max(0.0, self.player.shield_timer - 1.0)
            else:
                self.player.hp -= 1
            self.effects.add(Explosion(e.pos))
            self.shake.bump(9)
            self.player.invuln = 0.6

        # pickup powerups
        for p in [pp for pp in self.powerups if self.player.rect.colliderect(pp.rect)]:
            if p.kind == "shield":
                self.player.shield_timer += 6.0
                self.floaters.add(FloatingText(self.player.pos, "SHIELD", CYAN))
            elif p.kind == "rapid":
                self.player.rapid_timer += 6.0
                self.floaters.add(FloatingText(self.player.pos, "RAPID FIRE", PURPLE))
            else:
                self.player.hp = min(PLAYER_MAX_HP, self.player.hp + 2)
                self.floaters.add(FloatingText(self.player.pos, "+2 HP", GREEN))
            self.shake.bump(4)
            p.kill()

        if self.player.hp <= 0:
            self.game_over = True
            for _ in range(10):
                self.effects.add(Explosion(self.player.pos + Vector2(random.uniform(-40,40), random.uniform(-40,40))))

    # -------------------- Rendering -------------------- #
    def draw(self):
        self.screen.fill(BLACK)

        # parallax starfield
        for i, s in enumerate(self.stars):
            c = 140 + int((self.star_speed[i]-60) / 140 * 100)
            pygame.draw.circle(self.screen, (c, c, c), (int(s.x), int(s.y)), 2 if self.star_speed[i] < 120 else 3)

        # camera shake offset
        off = self.shake.offset()
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        # sprites
        for e in self.enemies: e.draw(layer)
        if self.boss.sprite: self.boss.sprite.draw(layer)
        for b in self.all_bullets: b.draw(layer)
        for b in self.enemy_bullets: b.draw(layer)
        for p in self.powerups: p.draw(layer)
        for fx in self.effects: fx.draw(layer)
        self.player.draw(layer)
        for ft in self.floaters: ft.draw(layer, self.font_small)

        self.screen.blit(layer, off)

        # UI
        score_img = self.font_big.render(f"Score: {self.player.score}", True, WHITE)
        self.screen.blit(score_img, (20, 20))
        if self.player.rapid_timer > 0:
            t = self.font_small.render(f"Rapid: {self.player.rapid_timer:0.1f}s", True, PURPLE)
            self.screen.blit(t, (20, 60))
        if self.player.shield_timer > 0:
            t = self.font_small.render(f"Shield: {self.player.shield_timer:0.1f}s", True, CYAN)
            self.screen.blit(t, (20, 80))
        if self.paused:
            self.draw_center_text("PAUSED — press P to resume", 0)
        if self.game_over:
            self.draw_center_text("Game Over — Press ESC to quit", -20)

        pygame.display.flip()

    def draw_center_text(self, text, dy=0):
        img = self.font_big.render(text, True, WHITE)
        rect = img.get_rect(center=(WIDTH/2, HEIGHT/2 + dy))
        self.screen.blit(img, rect)


if __name__ == "__main__":
    try:
        Game().run()
    except Exception as e:
        print("Fatal error:", e)
        pygame.quit()
        sys.exit(1)
