import pygame
import random
import time
import math
from enum import Enum
import heapq
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
import asyncio

# 게임 설정
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
MAZE_WIDTH = 25  # 미로의 가로 타일 수
MAZE_HEIGHT = 25 # 미로의 세로 타일 수
TILE_SIZE = 20   # 각 타일의 크기 (픽셀)

# UI 영역을 위해 화면 너비 확장
SCREEN_WIDTH_WITH_UI = MAZE_WIDTH * TILE_SIZE + 300 # 미로 + UI 공간

# 색상 정의
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
WALL_COLOR = (100, 100, 100)
PLAYER_COLOR = (0, 128, 255)
STAR_COLOR = (255, 255, 0)
EXIT_COLOR = (0, 200, 0)
FOG_COLOR = (30, 30, 30) # 시야 밖 영역 색상
MINIMAP_ITEM_COLOR = (100, 200, 255) # 미니맵 아이템 색상 (하늘색)
EVENT_BOX_COLOR = (150, 0, 150) # 이벤트 상자 색상 (보라색)

# AI 색상
PATROL_AI_COLOR = (255, 0, 0)      # 순찰 AI (빨강)
DETECTOR_AI_COLOR = (0, 255, 255)  # 탐지 AI (청록)
ENHANCED_AI_COLOR = (255, 165, 0)  # 강화 AI (주황)

# UI 색상
UI_BG_COLOR = (50, 50, 50)
WARNING_RED = (255, 50, 50)
WARNING_YELLOW = (255, 255, 50)

# 게임 상태 Enum
class GameState(Enum):
    MENU = 1
    PLAYING = 2
    WON = 3
    LOST = 4

# AI 타입 Enum
class AIType(Enum):
    PATROL = 1
    DETECTOR = 2
    ENHANCED = 3

# 이벤트 타입 Enum
class EventType(Enum):
    INVINCIBLE = 1      # 무적
    WALL_PASS = 2       # 벽 통과
    MAP_DARK = 3        # 맵 전체 어두워짐
    ENEMY_SPEED_UP = 4  # 적 속도 증가

# 시야 및 게임 시간
VISION_RADIUS = 5 # 플레이어 시야 반경 (타일 단위)
GAME_TIME_LIMIT = 300 # 게임 시간 제한 (초)

### **Position 클래스**
@dataclass
class Position:
    x: int
    y: int

    def __add__(self, other):
        return Position(self.x + other.x, self.y + other.y)

    def distance_to(self, other):
        """두 위치 간의 유클리드 거리 반환"""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def __lt__(self, other):
        # heapq에서 사용하기 위한 비교 연산자 정의
        if self.x == other.x:
            return self.y < other.y
        return self.x < other.x
    
    def __hash__(self):
        # 딕셔너리 키로 사용하기 위한 해시 함수 정의
        return hash((self.x, self.y))

    def __eq__(self, other):
        # 동일성 비교를 위한 동등 연산자 정의
        if not isinstance(other, Position):
            return NotImplemented
        return self.x == other.x and self.y == other.y


class MazeGenerator:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.maze = [[1 for _ in range(width)] for _ in range(height)]
        
    def generate(self):
        # 미로 생성 알고리즘 (DFS 기반)
        stack = [(1, 1)]
        self.maze[1][1] = 0
        
        directions = [(0, 2), (2, 0), (0, -2), (-2, 0)]
        
        while stack:
            current_x, current_y = stack[-1]
            neighbors = []
            
            for dx, dy in directions:
                nx, ny = current_x + dx, current_y + dy
                if 1 <= nx < self.width-1 and 1 <= ny < self.height-1:
                    if self.maze[ny][nx] == 1:
                        neighbors.append((nx, ny, current_x + dx//2, current_y + dy//2))
            
            if neighbors:
                nx, ny, mx, my = random.choice(neighbors)
                self.maze[ny][nx] = 0
                self.maze[my][mx] = 0
                stack.append((nx, ny))
            else:
                stack.pop()
        
        # 일부 벽을 제거하여 더 복잡한 경로 생성
        for _ in range(self.width * self.height // 20):
            x = random.randint(1, self.width-2)
            y = random.randint(1, self.height-2)
            if self.maze[y][x] == 1:
                neighbors_count = sum(1 for dx, dy in [(0,1),(1,0),(0,-1),(-1,0)] 
                                    if self.maze[y+dy][x+dx] == 0)
                if neighbors_count >= 2:
                    self.maze[y][x] = 0
        
        # 시작점은 항상 통로
        self.maze[1][1] = 0 
        
        return self.maze

class Player:
    def __init__(self, x, y):
        self.pos = Position(x, y)
        self.stars_collected = 0
        self.sprint_cooldown = 0 # 스프린트 쿨다운 시간
        self.stealth_charges = 5 # 은신 사용 가능 횟수
        self.stealth_active = 0  # 은신 활성화 시간 (0이면 비활성화)
        self.last_move_time = 0
        self.move_delay = 0.15   # 기본 이동 딜레이
        self.last_move_direction = (0, 0) # 마지막 이동 방향 (x, y)
        self.game_instance = None

        self.invincible_until = 0 # 무적 시간 종료
        self.wall_pass_until = 0  # 벽 통과 시간 종료

    def move(self, dx, dy, maze):
        """플레이어 이동 처리"""
        current_time = time.time()
        
        is_sprinting = pygame.key.get_pressed()[pygame.K_LSHIFT] and self.sprint_cooldown <= 0
        
        move_delay_factor = 0.5 if is_sprinting else 1.0 # 스프린트 시 이동 딜레이 절반

        if current_time - self.last_move_time < self.move_delay * move_delay_factor:
            return False

        new_x, new_y = self.pos.x + dx, self.pos.y + dy

        if not (0 <= new_x < MAZE_WIDTH and 0 <= new_y < MAZE_HEIGHT):
            return False # 미로 밖으로는 이동 불가

        # 벽 통과 상태 확인
        if self.is_wall_passing() or maze[new_y][new_x] == 0:
            self.pos = Position(new_x, new_y)
            self.last_move_time = current_time
            self.last_move_direction = (dx, dy) # 마지막 이동 방향 업데이트
            return True
        return False
    
    def set_game_instance(self, game_instance):
        """게임 인스턴스를 설정하는 메서드 (AI와 유사)"""
        self.game_instance = game_instance

    def activate_stealth(self):
        """은신 활성화"""
        if self.stealth_charges > 0 and self.stealth_active == 0:
            self.stealth_active = time.time() + 5.0 # 5초간 은신 활성화
            self.stealth_charges -= 1
            if self.game_instance: # 메시지 시스템 활용
                self.game_instance.add_game_message("은신 활성화!")
    
    def is_stealthed(self):
        """은신 활성화 여부 반환"""
        if self.stealth_active > 0:
            if time.time() < self.stealth_active:
                return True
            else:
                self.stealth_active = 0 # 은신 시간 만료
                if self.game_instance: # 메시지 시스템 활용
                    self.game_instance.add_game_message("은신 해제")
        return False
    
    def get_stealth_remaining_time(self):
        """은신 남은 시간 반환 (초)"""
        if self.stealth_active > 0:
            return max(0, self.stealth_active - time.time())
        return 0

    def is_invincible(self):
        """무적 상태 여부 반환"""
        return time.time() < self.invincible_until
    
    def get_invincible_remaining_time(self):
        """무적 남은 시간 반환 (초)"""
        if self.is_invincible():
            return max(0, self.invincible_until - time.time())
        return 0

    def is_wall_passing(self):
        """벽 통과 상태 여부 반환"""
        return time.time() < self.wall_pass_until

    def get_wall_pass_remaining_time(self):
        """벽 통과 남은 시간 반환 (초)"""
        if self.is_wall_passing():
            return max(0, self.wall_pass_until - time.time())
        return 0


class AI:
    def __init__(self, x, y, ai_type: AIType, game_instance):
        self.pos = Position(x, y)
        self.type = ai_type
        self.game_instance = game_instance # StarMazeGame 인스턴스 참조
        self.last_move_time = 0
        self.patrol_path = []
        self.path_index = 0
        self.chase_path = [] # 추적 경로

        self.base_move_delay = 0 # 기본 이동 딜레이 (초기화 시 설정)
        self.vision_radius = 0 # 시야 반경 (초기화 시 설정)
        
        # AI 타입에 따른 고유 속성 설정
        if self.type == AIType.PATROL:
            self.base_move_delay = 0.3 # 순찰 AI 이동 딜레이 (기본)
            self.vision_radius = 7 # 순찰 AI 시야 반경
            self.is_chasing = False # 순찰 AI의 추적 상태
            self.last_known_player_pos = None # 순찰 AI가 플레이어를 마지막으로 본 위치
        elif self.type == AIType.DETECTOR:
            self.base_move_delay = 0.5 # 탐지 AI 이동 딜레이 (느리게)
            self.vision_radius = float('inf') # 탐지 AI는 항상 플레이어 위치를 앎
        elif self.type == AIType.ENHANCED:
            self.base_move_delay = 0.25 # 강화 AI 이동 딜레이 (빠르게)
            self.last_known_pos = None # 강화 AI를 위한 마지막 플레이어 위치 (예측용)
        
        self.current_move_delay = self.base_move_delay # 현재 적용되는 이동 딜레이

    def get_color(self):
        """AI 타입에 따른 색상 반환"""
        if self.type == AIType.PATROL:
            return PATROL_AI_COLOR
        elif self.type == AIType.DETECTOR:
            return DETECTOR_AI_COLOR
        elif self.type == AIType.ENHANCED:
            return ENHANCED_AI_COLOR
        return WHITE

    def can_move(self, maze):
        """AI가 이동할 수 있는지 확인 (딜레이 기반)"""
        current_time = time.time()
        if current_time - self.last_move_time < self.current_move_delay: # current_move_delay 사용
            return False
        self.last_move_time = current_time
        return True

    def move_to(self, target_pos: Position, maze):
        """AI를 목표 위치로 이동"""
        if self.chase_path:
            next_step = self.chase_path[0]
            if 0 <= next_step.x < MAZE_WIDTH and 0 <= next_step.y < MAZE_HEIGHT and maze[next_step.y][next_step.x] == 0:
                self.pos = next_step
                self.chase_path.pop(0) # 다음 스텝으로 이동했으니 경로에서 제거
                return True
        return False

    def set_patrol_path(self, path: List[Position]):
        """순찰 경로 설정"""
        self.patrol_path = path
        self.path_index = 0

    def set_chase_target(self, target_pos: Position):
        """추적 목표 설정 및 A* 경로 계산"""
        path = self.game_instance.find_path_astar(self.pos, target_pos) 
        self.chase_path = path

    def _patrol_behavior(self, player_pos, player_stealthed, maze):
        """순찰 AI 행동 로직: 평소 순찰, 플레이어 시야 내 추적"""
        player_in_sight = not player_stealthed and self.pos.distance_to(player_pos) < self.vision_radius

        if player_in_sight:
            # 플레이어 발견 시 추적
            if not self.is_chasing or self.last_known_player_pos != player_pos:
                self.set_chase_target(player_pos)
                self.is_chasing = True
                self.last_known_player_pos = player_pos
        elif self.is_chasing:
            # 추적 중 플레이어를 놓쳤고, 마지막으로 본 위치에 도달했다면 순찰로 복귀
            if self.pos == self.last_known_player_pos or not self.chase_path:
                self.is_chasing = False
                self.chase_path = [] # 추적 경로 초기화
                self.last_known_player_pos = None
            else: # 마지막으로 본 위치로 계속 이동
                self.move_to(self.chase_path[0], maze)
                return # 추적 행동 계속

        # 순찰 또는 추적 중인 상태가 아니면 순찰 경로를 따름
        if not self.is_chasing:
            if self.patrol_path:
                # 다음 순찰 지점에 도달했으면 인덱스 업데이트
                if self.pos == self.patrol_path[self.path_index]:
                    self.path_index = (self.path_index + 1) % len(self.patrol_path)
                
                # 다음 순찰 지점으로 A* 경로 계산 및 이동
                self.set_chase_target(self.patrol_path[self.path_index])
                if self.chase_path:
                    self.move_to(self.chase_path[0], maze)
        elif self.chase_path: # 플레이어를 추적 중이고 경로가 있으면 이동
            self.move_to(self.chase_path[0], maze)


    def _detector_behavior(self, player_pos, player_stealthed, maze):
        """탐지 AI 행동 로직: 항상 플레이어 위치를 알고 추격"""
        # 은신 중이 아니면 플레이어의 위치를 항상 알고 추격
        if not player_stealthed:
            self.set_chase_target(player_pos)
        else: # 은신 중이면, 마지막으로 본 위치 (현재 위치)에 머무름
            # 또는 마지막으로 본 위치가 없다면 (즉 처음부터 은신 중이었다면) 제자리에 머무름
            if not self.chase_path: # 추적 경로가 없다면 (처음이거나 놓쳤을 때)
                self.set_chase_target(self.pos) # 현재 위치를 목표로 설정하여 움직이지 않음
        
        if self.chase_path:
            self.move_to(self.chase_path[0], maze)

    def _enhanced_behavior(self, player, maze_data): # player 객체와 maze_data (미로 리스트)를 받도록 수정
        """강화 AI 행동 로직 (플레이어의 움직임 예측)"""
        # 더 빠르고 지능적인 추적
        if not player.is_stealthed(): # player 객체를 통해 is_stealthed() 호출
            prediction_steps = 3 # 3칸 앞을 예측

            # 플레이어의 마지막 이동 방향을 기반으로 예측 위치 계산
            predicted_pos = Position(
                player.pos.x + player.last_move_direction[0] * prediction_steps,
                player.pos.y + player.last_move_direction[1] * prediction_steps
            )

            # 예측 위치가 미로 밖이거나 벽이면 그냥 현재 위치 추적
            if not (0 <= predicted_pos.x < MAZE_WIDTH and 0 <= predicted_pos.y < MAZE_HEIGHT and
                    maze_data[predicted_pos.y][predicted_pos.x] == 0): # 전달받은 maze_data 사용
                self.set_chase_target(player.pos)
            else:
                self.set_chase_target(predicted_pos)
            self.last_known_pos = player.pos # 플레이어가 은신하지 않을 때 마지막 위치 업데이트
        else: # 플레이어가 은신 중일 때
            # 마지막으로 본 위치로 이동하거나 무작위 순찰
            if self.last_known_pos:
                if self.pos == self.last_known_pos: # 마지막 위치에 도달하면 놓침으로 간주
                    self.last_known_pos = None
                    self.chase_path = [] # 경로 초기화
                else:
                    self.set_chase_target(self.last_known_pos)
            else: # 마지막 본 위치가 없으면 순찰 AI처럼 행동
                if not self.chase_path: 
                    target_x, target_y = random.randint(0, MAZE_WIDTH - 1), random.randint(0, MAZE_HEIGHT - 1)
                    while self.game_instance.maze[target_y][target_x] == 1: 
                        target_x, target_y = random.randint(0, MAZE_WIDTH - 1), random.randint(0, MAZE_HEIGHT - 1)
                    self.set_chase_target(Position(target_x, target_y))
        
        if self.chase_path:
            self.move_to(self.chase_path[0], maze_data)

    # AI의 update 메서드 (StarMazeGame.update에서 호출됨)
    def update(self, player, maze): # player 객체와 maze 리스트를 받도록 수정
        if not self.can_move(maze):
            return

        current_time = time.time()
        
        # 각 AI 타입에 따른 행동 로직 호출
        if self.type == AIType.PATROL:
            self._patrol_behavior(player.pos, player.is_stealthed(), maze)
        elif self.type == AIType.DETECTOR:
            self._detector_behavior(player.pos, player.is_stealthed(), maze)
        elif self.type == AIType.ENHANCED:
            self._enhanced_behavior(player, maze) # player 객체와 maze 리스트 전달


class StarMazeGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH_WITH_UI, SCREEN_HEIGHT))
        pygame.display.set_caption("Star Maze")
        self.clock = pygame.time.Clock()
        # 폰트 파일 경로를 프로젝트 내 상대 경로로 변경합니다.
        font_path = "assets/fonts/NanumGothic-Regular.ttf"

        try:
            self.font = pygame.font.Font(font_path, 24)
            self.large_font = pygame.font.Font(font_path, 48)
            self.small_font = pygame.font.Font(font_path, 18)
        except pygame.error: # pygame.error를 잡는 것이 더 정확합니다.
            print(f"폰트 파일 '{font_path}'를 찾을 수 없습니다. 기본 폰트를 사용합니다.")
            self.font = pygame.font.Font(None, 24)
            self.large_font = pygame.font.Font(None, 48)
            self.small_font = pygame.font.Font(None, 18)

        self.state = GameState.MENU
        self.maze = []
        self.player = None
        self.stars = []
        self.exit_pos = None # 초기에는 None으로 설정
        self.minimap_item_pos = None # 미니맵 아이템 위치 추가
        self.minimap_active_until = 0 # 미니맵 활성화 종료 시간
        self.event_box_pos = None # 이벤트 상자 위치 추가
        self.current_event = None # 현재 활성화된 이벤트 타입
        self.event_active_until = 0 # 이벤트 종료 시간
        self.ais = [] # AI 리스트 초기화
        self.start_time = 0
        self.game_messages = [] # (message_text, start_time, duration) 튜플 리스트


    def add_game_message(self, text, duration=2.0):
        """게임 화면에 표시될 메시지를 추가합니다."""
        self.game_messages.append((text, time.time(), duration))

    def draw_game_messages(self):
        """현재 활성화된 게임 메시지를 화면에 그립니다."""
        current_time = time.time()
        active_messages = []
        
        y_offset = SCREEN_HEIGHT - 50 # 화면 하단에서부터 메시지 표시 시작

        for i, (text, start_time, duration) in enumerate(self.game_messages):
            if current_time < start_time + duration:
                # 메시지 투명도 조절 (사라지기 직전에 서서히 투명해짐)
                alpha = 255
                fade_start_time = start_time + duration - 0.5 # 사라지기 0.5초 전부터 페이드 시작
                if current_time > fade_start_time:
                    alpha = int(255 * (1 - (current_time - fade_start_time) / 0.5))
                alpha = max(0, alpha) # 0 미만으로 내려가지 않게

                message_surface = self.font.render(text, True, (255, 255, 255))
                message_surface.set_alpha(alpha)
                
                text_rect = message_surface.get_rect(center=(SCREEN_WIDTH // 2, y_offset))
                self.screen.blit(message_surface, text_rect)
                y_offset -= 30 # 다음 메시지를 위해 위로 이동
                active_messages.append((text, start_time, duration))
        
        self.game_messages = active_messages # 활성화된 메시지만 남김

    def init_game(self):
        """게임 초기화"""
        maze_gen = MazeGenerator(MAZE_WIDTH, MAZE_HEIGHT)
        self.maze = maze_gen.generate()
        self.player = Player(1, 1) # 플레이어 시작 위치
        self.player.set_game_instance(self) # 플레이어에게 게임 인스턴스 전달
        self.exit_pos = None # 게임 시작 시 출구는 생성되지 않음
        self.minimap_item_pos = None # 미니맵 아이템 위치 초기화
        self.minimap_active_until = 0 # 미니맵 활성화 시간 초기화
        self.event_box_pos = None # 이벤트 상자 위치 초기화
        self.current_event = None # 현재 이벤트 초기화
        self.event_active_until = 0 # 이벤트 종료 시간 초기화
        self.generate_stars()
        self.generate_minimap_item() # 미니맵 아이템 생성 호출
        self.generate_event_box() # 이벤트 상자 생성 호출
        self.ais = [] # AI 리스트 초기화
        self.create_ais() # AI 생성
        self.start_time = time.time()
        self.state = GameState.PLAYING
        self.game_messages = [] # 새 게임 시작 시 메시지 초기화
        self.add_game_message("별 미로에 오신 것을 환영합니다!") # 시작 메시지
        self.add_game_message("별 5개를 모아 탈출구를 소환하세요!", duration=3.0)

    def generate_stars(self):
        """별 5개를 미로의 빈 공간에 무작위로 배치"""
        empty_spaces = []
        for y in range(len(self.maze)):
            for x in range(len(self.maze[0])):
                # 플레이어 시작점 주변은 피하고, 탈출구 위치(미생성 상태)는 고려하지 않음
                if (self.maze[y][x] == 0 and 
                    Position(x, y).distance_to(self.player.pos) > 5): # 플레이어 시작점에서 충분히 멀리
                    empty_spaces.append(Position(x, y))
        
        self.stars = random.sample(empty_spaces, min(5, len(empty_spaces)))
    
    def generate_minimap_item(self):
        """미니맵 아이템을 미로의 빈 공간에 무작위로 배치"""
        empty_spaces = []
        for y in range(len(self.maze)):
            for x in range(len(self.maze[0])):
                # 플레이어 시작점, 별 위치 등을 고려하여 배치
                is_clear = True
                current_pos = Position(x, y)
                if (self.maze[y][x] == 1 or 
                    current_pos == self.player.pos or 
                    current_pos.distance_to(self.player.pos) < 8): # 플레이어 시작점과 충분히 멀리
                    is_clear = False
                
                # 생성된 별 위치와도 겹치지 않게
                for star in self.stars:
                    if current_pos == star:
                        is_clear = False
                        break
                
                if is_clear:
                    empty_spaces.append(current_pos)
        
        if empty_spaces:
            # 적절한 위치에 아이템 하나만 배치
            self.minimap_item_pos = random.choice(empty_spaces)
            self.add_game_message("미니맵 아이템이 생성되었습니다!", duration=2.5)

    def generate_event_box(self):
        """이벤트 상자를 미로의 빈 공간에 무작위로 배치"""
        empty_spaces = []
        for y in range(len(self.maze)):
            for x in range(len(self.maze[0])):
                is_clear = True
                current_pos = Position(x, y)
                # 플레이어 시작점, 별, 미니맵 아이템 위치와 겹치지 않게
                if (self.maze[y][x] == 1 or 
                    current_pos == self.player.pos or 
                    current_pos.distance_to(self.player.pos) < 10): # 플레이어 시작점에서 충분히 멀리
                    is_clear = False
                
                # 생성된 별 위치와도 겹치지 않게
                for star in self.stars:
                    if current_pos == star:
                        is_clear = False
                        break
                
                # 미니맵 아이템 위치와도 겹치지 않게
                if self.minimap_item_pos and current_pos == self.minimap_item_pos:
                    is_clear = False
                
                if is_clear:
                    empty_spaces.append(current_pos)
        
        if empty_spaces:
            self.event_box_pos = random.choice(empty_spaces)
            self.add_game_message("미스터리 상자가 생성되었습니다!", duration=2.5)
        
    def activate_random_event(self):
        """랜덤 이벤트를 활성화합니다."""
        event_types = list(EventType)
        chosen_event = random.choice(event_types)
        
        self.current_event = chosen_event
        self.event_active_until = time.time() + 5.0 # 모든 이벤트는 5초 지속 (임의 설정)

        event_message = ""
        if chosen_event == EventType.INVINCIBLE:
            self.player.invincible_until = self.event_active_until
            event_message = "무적 5초!"
        elif chosen_event == EventType.WALL_PASS:
            self.player.wall_pass_until = self.event_active_until
            event_message = "벽 통과 5초!"
        elif chosen_event == EventType.MAP_DARK:
            event_message = "맵 전체 어두워짐 5초!"
        elif chosen_event == EventType.ENEMY_SPEED_UP:
            for ai in self.ais:
                ai.current_move_delay = ai.base_move_delay * 0.5 # AI 속도 2배 증가
            event_message = "적이 빨라졌습니다! 5초!"
        
        self.add_game_message(f"이벤트 발생: {event_message}", duration=3.0)

    def deactivate_current_event(self):
        """현재 활성화된 이벤트를 비활성화합니다."""
        if self.current_event == EventType.INVINCIBLE:
            self.player.invincible_until = 0
        elif self.current_event == EventType.WALL_PASS:
            self.player.wall_pass_until = 0
        elif self.current_event == EventType.MAP_DARK:
            # 특별히 해제할 것 없음 (draw_maze에서 자동으로 복구)
            pass
        elif self.current_event == EventType.ENEMY_SPEED_UP:
            for ai in self.ais:
                ai.current_move_delay = ai.base_move_delay # AI 속도 원래대로 복구
        
        self.current_event = None
        self.event_active_until = 0
        self.add_game_message("이벤트 종료!", duration=2.0)


    def create_ais(self):
        """AI들을 생성하고 초기 위치 설정"""
        empty_spaces = []
        for y in range(len(self.maze)):
            for x in range(len(self.maze[0])):
                # 플레이어 시작 위치, 미니맵 아이템 위치, 이벤트 상자 위치와 겹치지 않게
                is_clear = True
                current_pos = Position(x, y)
                if (self.maze[y][x] == 1 or 
                    current_pos.distance_to(self.player.pos) < 5 or # 플레이어 근처 피하기
                    (self.minimap_item_pos and current_pos == self.minimap_item_pos) or # 미니맵 아이템 위치 피하기
                    (self.event_box_pos and current_pos == self.event_box_pos) or # 이벤트 상자 위치 피하기
                    current_pos.distance_to(self.player.pos) > MAZE_WIDTH * 0.7 # 너무 먼 곳도 피해서 AI들이 초반부터 보일 가능성 높임
                    ):
                    is_clear = False
                
                if is_clear:
                    empty_spaces.append(current_pos)
        
        # 최소 2개의 AI가 생성될 수 있도록 충분한 공간 확보 확인
        if len(empty_spaces) >= 2: 
            # 순찰 AI 생성
            patrol_pos = random.choice(empty_spaces)
            patrol_ai = AI(patrol_pos.x, patrol_pos.y, AIType.PATROL, self)
            patrol_path = self.generate_patrol_path(patrol_pos) # 순찰 AI는 순찰 경로 가짐
            patrol_ai.set_patrol_path(patrol_path)
            self.ais.append(patrol_ai)
            empty_spaces.remove(patrol_pos) # 사용된 위치 제거

            # 탐지 AI 생성
            detector_pos = random.choice(empty_spaces)
            detector_ai = AI(detector_pos.x, detector_pos.y, AIType.DETECTOR, self)
            self.ais.append(detector_ai)
            empty_spaces.remove(detector_pos) # 사용된 위치 제거


    def find_path_astar(self, start_pos: Position, end_pos: Position) -> List[Position]:
        """A* 알고리즘을 사용해 start_pos에서 end_pos까지의 최단 경로를 찾습니다."""
        
        def heuristic(a, b):
            # 맨해튼 거리 휴리스틱 함수
            return abs(a.x - b.x) + abs(a.y - b.y)

        open_set = []
        heapq.heappush(open_set, (0, start_pos)) # (f_score, position)
        
        came_from = {}
        # 딕셔너리 키로 Position 객체 대신 튜플 (x, y) 사용
        g_score = {(x, y): float('inf') for y in range(MAZE_HEIGHT) for x in range(MAZE_WIDTH)}
        g_score[(start_pos.x, start_pos.y)] = 0
        
        f_score = {(x, y): float('inf') for y in range(MAZE_HEIGHT) for x in range(MAZE_WIDTH)}
        f_score[(start_pos.x, start_pos.y)] = heuristic(start_pos, end_pos)

        open_set_hash = {(start_pos.x, start_pos.y)}

        while open_set:
            _, current = heapq.heappop(open_set) 
            open_set_hash.remove((current.x, current.y))

            if current.x == end_pos.x and current.y == end_pos.y : 
                path = []
                while (current.x, current.y) in came_from:
                    path.append(current)
                    current = came_from[(current.x, current.y)]
                path.reverse()
                return path

            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                neighbor = Position(current.x + dx, current.y + dy)

                if not (0 <= neighbor.x < MAZE_WIDTH and 0 <= neighbor.y < MAZE_HEIGHT):
                    continue
                if self.maze[neighbor.y][neighbor.x] == 1:
                    continue

                tentative_g_score = g_score.get((current.x, current.y), float('inf')) + 1

                if tentative_g_score < g_score.get((neighbor.x, neighbor.y), float('inf')):
                    came_from[(neighbor.x, neighbor.y)] = current
                    g_score[(neighbor.x, neighbor.y)] = tentative_g_score
                    f_score[(neighbor.x, neighbor.y)] = tentative_g_score + heuristic(neighbor, end_pos)
                    if (neighbor.x, neighbor.y) not in open_set_hash:
                        heapq.heappush(open_set, (f_score[(neighbor.x, neighbor.y)], neighbor))
                        open_set_hash.add((neighbor.x, neighbor.y))
        
        return [] # 경로를 찾지 못한 경우
    
    def generate_patrol_path(self, start_pos):
        """AI를 위한 순찰 경로 생성"""
        path = [start_pos]
        current = start_pos
        
        for _ in range(8):  # 8개 포인트의 순찰 경로
            possible_moves = []
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                new_x, new_y = current.x + dx*3, current.y + dy*3
                if (0 <= new_x < MAZE_WIDTH and 0 <= new_y < MAZE_HEIGHT and
                    self.maze[new_y][new_x] == 0):
                    possible_moves.append(Position(new_x, new_y))
            
            if possible_moves:
                current = random.choice(possible_moves)
                path.append(current)
        
        return path
    
    def generate_exit_point(self):
        """별 5개 수집 시 맵 가장자리에 탈출구를 생성합니다."""
        
        # 미로의 가장자리 좌표들을 수집합니다.
        # 벽이 아닌 통로여야 합니다.
        possible_exit_points = []
        
        # 미로 테두리 한 칸 안쪽 (실질적인 가장자리 통로)
        # 상단 가장자리
        for x in range(1, MAZE_WIDTH - 1): 
            if self.maze[1][x] == 0: 
                possible_exit_points.append(Position(x, 1))
        # 하단 가장자리
        for x in range(1, MAZE_WIDTH - 1): 
            if self.maze[MAZE_HEIGHT - 2][x] == 0: 
                possible_exit_points.append(Position(x, MAZE_HEIGHT - 2))
        # 좌측 가장자리
        for y in range(1, MAZE_HEIGHT - 1): 
            if self.maze[y][1] == 0: 
                possible_exit_points.append(Position(1, y))
        # 우측 가장자리
        for y in range(1, MAZE_HEIGHT - 1): 
            if self.maze[y][MAZE_WIDTH - 2] == 0: 
                possible_exit_points.append(Position(MAZE_WIDTH - 2, y))

        # 플레이어 위치 근처는 피합니다.
        safe_exit_points = [
            p for p in possible_exit_points 
            if p.distance_to(self.player.pos) > VISION_RADIUS + 3 # 시야 반경보다 더 멀리
        ]
        
        if safe_exit_points:
            self.exit_pos = random.choice(safe_exit_points)
            self.add_game_message("탈출구가 생성되었습니다! 찾아보세요!", duration=3.0)
        else:
            # 만약 안전한 위치를 찾지 못하면, 일단 플레이어 위치와 상관없이 생성 (비상용)
            if possible_exit_points:
                self.exit_pos = random.choice(possible_exit_points)
                self.add_game_message("탈출구가 생성되었습니다! (경고: 플레이어 근처)", duration=3.0)
            else:
                # 정말 극단적인 경우 생성 불가능할 때 (발생해서는 안 됨)
                self.add_game_message("오류: 탈출구를 생성할 수 없습니다!", duration=5.0)

    def get_star_directions(self):
        """수집하지 않은 별들의 방향 정보 반환"""
        directions = []
        player_pos = self.player.pos
        
        for star in self.stars:
            dx = star.x - player_pos.x
            dy = star.y - player_pos.y
            
            # 8방향으로 방향 결정
            if abs(dx) > abs(dy):
                if dx > 0:
                    direction = "동쪽" if abs(dy) < abs(dx)/2 else ("남동쪽" if dy > 0 else "북동쪽")
                else:
                    direction = "서쪽" if abs(dy) < abs(dx)/2 else ("남서쪽" if dy > 0 else "북서쪽")
            else:
                if dy > 0:
                    direction = "남쪽" if abs(dx) < abs(dy)/2 else ("남동쪽" if dx > 0 else "남서쪽")
                else:
                    direction = "북쪽" if abs(dx) < abs(dy)/2 else ("북동쪽" if dx > 0 else "북서쪽")
            
            directions.append(direction)
        
        return directions
    
    def handle_input(self):
        keys = pygame.key.get_pressed()
        
        if self.state == GameState.PLAYING:
            moved = False
            sprint_active = keys[pygame.K_LSHIFT] and self.player.sprint_cooldown <= 0
            
            # 플레이어 이동 입력 처리
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                moved = self.player.move(0, -1, self.maze)
            elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
                moved = self.player.move(0, 1, self.maze)
            elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
                moved = self.player.move(-1, 0, self.maze)
            elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                moved = self.player.move(1, 0, self.maze)
            
            # 스프린트 활성화 및 이동 시 쿨다운 적용
            if sprint_active and moved:
                self.player.sprint_cooldown = time.time() + 3.0  # 3초 쿨다운
        
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and self.state == GameState.PLAYING:
                    self.player.activate_stealth()
                elif event.key == pygame.K_r and self.state in [GameState.WON, GameState.LOST]:
                    self.init_game()
                elif event.key == pygame.K_RETURN and self.state == GameState.MENU:
                    self.init_game()
        
        return True
    
    def update(self):
        if self.state != GameState.PLAYING:
            return
        
        current_time = time.time()
        
        # 시간 제한 확인
        if current_time - self.start_time > GAME_TIME_LIMIT:
            self.state = GameState.LOST
            return
        
        # 별 수집 확인
        for star in self.stars[:]: # 리스트 복사본을 사용하여 반복 중 삭제 가능
            if self.player.pos.x == star.x and self.player.pos.y == star.y:
                self.stars.remove(star)
                self.player.stars_collected += 1
                self.add_game_message(f"별 획득! ({self.player.stars_collected}/5)")
                
                # 3개 이상 수집 시 강화 AI 생성 (이미 생성되지 않은 경우)
                if self.player.stars_collected == 3 and not any(ai.type == AIType.ENHANCED for ai in self.ais):
                    self.spawn_enhanced_ai()
                
                # 별 5개 모두 수집 시 탈출구 생성
                if self.player.stars_collected == 5 and self.exit_pos is None:
                    self.generate_exit_point() # 탈출구 생성 함수 호출

        # 미니맵 아이템 획득 확인
        if self.minimap_item_pos and self.player.pos == self.minimap_item_pos:
            self.minimap_active_until = current_time + 5.0 # 5초간 미니맵 활성화
            self.minimap_item_pos = None # 아이템 제거
            self.add_game_message("미니맵 활성화! 5초간 전체 지도가 보입니다!", duration=3.0)

        # 이벤트 상자 획득 확인
        if self.event_box_pos and self.player.pos == self.event_box_pos:
            self.event_box_pos = None # 상자 제거
            self.activate_random_event() # 랜덤 이벤트 활성화

        # 이벤트 종료 확인
        if self.current_event and current_time >= self.event_active_until:
            self.deactivate_current_event()

        # 승리 조건 확인
        # 플레이어가 별 5개를 모두 모았고, 탈출구가 생성되었으며, 플레이어가 탈출구 위치에 도달했을 때
        if (self.player.stars_collected == 5 and 
            self.exit_pos is not None and # 탈출구가 생성되었는지 확인
            self.player.pos.x == self.exit_pos.x and 
            self.player.pos.y == self.exit_pos.y):
            self.state = GameState.WON
            return
            
        # AI 업데이트
        for ai in self.ais:
            ai.update(self.player, self.maze)  
            
            # AI와 플레이어 충돌 확인 (플레이어가 은신 중이 아니고 무적 상태가 아닐 때만)
            if (ai.pos.x == self.player.pos.x and 
                ai.pos.y == self.player.pos.y and
                not self.player.is_stealthed() and 
                not self.player.is_invincible()): # 무적 상태 확인
                self.state = GameState.LOST
                return
    
    def spawn_enhanced_ai(self):
        """강화 AI 생성"""
        empty_spaces = []
        for y in range(len(self.maze)):
            for x in range(len(self.maze[0])):
                # 플레이어 위치 근처는 피합니다.
                if (self.maze[y][x] == 0 and 
                    Position(x, y).distance_to(self.player.pos) > 8):
                    empty_spaces.append(Position(x, y))
        
        if empty_spaces:
            enhanced_pos = random.choice(empty_spaces)
            enhanced_ai = AI(enhanced_pos.x, enhanced_pos.y, AIType.ENHANCED, self)
            self.ais.append(enhanced_ai)
            self.add_game_message("강화 AI가 생성되었습니다!", duration=3.0)

    def draw_star(self, surface, color, pos, size):
        """
        주어진 위치에 5개의 꼭지점을 가진 별을 그립니다.
        :param surface: 그릴 Pygame Surface
        :param color: 별의 색상 (R, G, B)
        :param pos: 별의 중심 위치 (Position 객체 또는 (x, y) 튜플)
        :param size: 별의 크기 (대략적인 반지름)
        """
        if isinstance(pos, Position):
            center_x, center_y = pos.x * TILE_SIZE + TILE_SIZE // 2, pos.y * TILE_SIZE + TILE_SIZE // 2
        else:
            center_x, center_y = pos[0] * TILE_SIZE + TILE_SIZE // 2, pos[1] * TILE_SIZE + TILE_SIZE // 2

        outer_radius = size
        inner_radius = size * 0.4  # 별의 안쪽 반지름 (뾰족한 정도)
        num_points = 5

        points = []
        for i in range(num_points * 2):
            radius = outer_radius if i % 2 == 0 else inner_radius
            angle = math.pi / num_points * i
            
            x = center_x + radius * math.sin(angle)
            y = center_y - math.cos(angle) * radius # Pygame y축은 아래로 갈수록 증가
            points.append((x, y))

        if len(points) >= 3: # 폴리곤은 최소 3개의 점이 필요합니다.
            pygame.draw.polygon(surface, color, points)

    def draw_minimap_item(self, surface, color, pos, size):
        """
        미니맵 아이템을 그립니다 (작은 원으로).
        :param surface: 그릴 Pygame Surface
        :param color: 아이템 색상
        :param pos: 아이템 위치 (Position 객체)
        :param size: 아이템 크기 (반지름)
        """
        center_x, center_y = pos.x * TILE_SIZE + TILE_SIZE // 2, pos.y * TILE_SIZE + TILE_SIZE // 2
        pygame.draw.circle(surface, color, (center_x, center_y), size)

    def draw_event_box(self, surface, color, pos):
        """
        이벤트 상자를 그립니다 (작은 사각형으로).
        :param surface: 그릴 Pygame Surface
        :param color: 상자 색상
        :param pos: 상자 위치 (Position 객체)
        """
        screen_x = pos.x * TILE_SIZE + TILE_SIZE // 4
        screen_y = pos.y * TILE_SIZE + TILE_SIZE // 4
        pygame.draw.rect(surface, color, (screen_x, screen_y, TILE_SIZE // 2, TILE_SIZE // 2))


    def draw_entities(self):
        """플레이어, 별, AI, 탈출구, 미니맵 아이템, 이벤트 상자 그리기"""
        player_x, player_y = self.player.pos.x, self.player.pos.y
        
        # 시야 전체 적용 여부 (미니맵 활성화 또는 맵 어두워짐 이벤트가 아닐 때)
        is_full_vision = time.time() < self.minimap_active_until and self.current_event != EventType.MAP_DARK

        # 별 그리기
        for star in self.stars:
            dx, dy = star.x - player_x, star.y - player_y
            if is_full_vision or (dx*dx + dy*dy <= VISION_RADIUS ** 2 and self.current_event != EventType.MAP_DARK):
                self.draw_star(self.screen, STAR_COLOR, star, TILE_SIZE // 2 - 2)
        
        # 탈출구 그리기 (self.exit_pos가 None이 아닐 때만)
        if self.exit_pos is not None:
            dx, dy = self.exit_pos.x - player_x, self.exit_pos.y - player_y
            if is_full_vision or (dx*dx + dy*dy <= VISION_RADIUS ** 2 and self.current_event != EventType.MAP_DARK):
                screen_x = self.exit_pos.x * TILE_SIZE
                screen_y = self.exit_pos.y * TILE_SIZE
                pygame.draw.rect(self.screen, EXIT_COLOR, 
                                 (screen_x, screen_y, TILE_SIZE, TILE_SIZE))
        
        # 미니맵 아이템 그리기 (현재 위치에 있고 아직 획득하지 않았을 때)
        if self.minimap_item_pos:
            dx, dy = self.minimap_item_pos.x - player_x, self.minimap_item_pos.y - player_y
            if is_full_vision or (dx*dx + dy*dy <= VISION_RADIUS ** 2 and self.current_event != EventType.MAP_DARK):
                 self.draw_minimap_item(self.screen, MINIMAP_ITEM_COLOR, self.minimap_item_pos, TILE_SIZE // 3)

        # 이벤트 상자 그리기 (현재 위치에 있고 아직 획득하지 않았을 때)
        if self.event_box_pos:
            dx, dy = self.event_box_pos.x - player_x, self.event_box_pos.y - player_y
            if is_full_vision or (dx*dx + dy*dy <= VISION_RADIUS ** 2 and self.current_event != EventType.MAP_DARK):
                self.draw_event_box(self.screen, EVENT_BOX_COLOR, self.event_box_pos)

        # AI 그리기
        for ai in self.ais:
            dx, dy = ai.pos.x - player_x, ai.pos.y - player_y
            if is_full_vision or (dx*dx + dy*dy <= VISION_RADIUS ** 2 and self.current_event != EventType.MAP_DARK):
                screen_x = ai.pos.x * TILE_SIZE + 2
                screen_y = ai.pos.y * TILE_SIZE + 2
                pygame.draw.circle(self.screen, ai.get_color(), 
                                   (screen_x + TILE_SIZE//2 - 2, screen_y + TILE_SIZE//2 - 2), 
                                   TILE_SIZE//2 - 2)
        # 플레이어 그리기
        screen_x = player_x * TILE_SIZE + 2
        screen_y = player_y * TILE_SIZE + 2
        color = PLAYER_COLOR
        if self.player.is_stealthed():
            color = (color[0]//2, color[1]//2, color[2]//2)  # 은신 시 어둡게
        elif self.player.is_invincible():
            # 무적 상태일 때 색상 변경 (예: 흰색 테두리)
            pygame.draw.rect(self.screen, (255, 255, 255), (screen_x-2, screen_y-2, TILE_SIZE, TILE_SIZE), 2) # 테두리
            color = PLAYER_COLOR # 내부 색상은 유지
        
        pygame.draw.rect(self.screen, color, 
                         (screen_x, screen_y, TILE_SIZE-4, TILE_SIZE-4))
    
        # 은신 남은 시간 게임 화면 내 표시
        stealth_remaining = self.player.get_stealth_remaining_time()
        if stealth_remaining > 0:
            stealth_timer_text = self.large_font.render(f"은신: {stealth_remaining:.1f}초", True, (0, 255, 0))
            alpha_value = 180
            stealth_timer_text.set_alpha(alpha_value)
            text_rect = stealth_timer_text.get_rect(center=(MAZE_WIDTH * TILE_SIZE // 2, 50))
            self.screen.blit(stealth_timer_text, text_rect)

    def draw_maze(self):
        """시야 제한을 적용한 미로 그리기 (미니맵 활성화 또는 맵 어두워짐 이벤트 적용)"""
        player_x, player_y = self.player.pos.x, self.player.pos.y
        
        # 미니맵 활성화 여부 확인
        minimap_active = time.time() < self.minimap_active_until
        # 맵 어두워짐 이벤트 활성화 여부 확인
        map_dark_active = self.current_event == EventType.MAP_DARK and time.time() < self.event_active_until

        for y in range(len(self.maze)):
            for x in range(len(self.maze[0])):
                screen_x = x * TILE_SIZE
                screen_y = y * TILE_SIZE
                
                # 시야 범위 확인 (미니맵 활성화 시 항상 True, 맵 어두워짐 시 항상 False)
                if minimap_active:
                    in_vision = True
                elif map_dark_active: # 맵 어두워짐 이벤트 시, 플레이어 위치만 보임
                    in_vision = (x == player_x and y == player_y)
                else: # 일반 시야 제한
                    in_vision = math.sqrt((x - player_x)**2 + (y - player_y)**2) <= VISION_RADIUS
                
                if in_vision:
                    # 벽과 바닥 그리기
                    if self.maze[y][x] == 1:
                        pygame.draw.rect(self.screen, WALL_COLOR, 
                                         (screen_x, screen_y, TILE_SIZE, TILE_SIZE))
                    else:
                        pygame.draw.rect(self.screen, BLACK, 
                                         (screen_x, screen_y, TILE_SIZE, TILE_SIZE))
                else:
                    # 시야 밖은 어둡게
                    pygame.draw.rect(self.screen, FOG_COLOR, 
                                     (screen_x, screen_y, TILE_SIZE, TILE_SIZE))

    def draw_ui(self):
        """UI 요소 그리기 (동적 y좌표 관리로 겹침 방지)"""
        # UI 배경
        ui_rect = pygame.Rect(MAZE_WIDTH * TILE_SIZE, 0, 
                              SCREEN_WIDTH_WITH_UI - MAZE_WIDTH * TILE_SIZE, SCREEN_HEIGHT)
        pygame.draw.rect(self.screen, UI_BG_COLOR, ui_rect)
        
        # --- 동적 Y 좌표 관리를 위한 변수 ---
        x_padding = MAZE_WIDTH * TILE_SIZE + 10 # UI 영역의 x 시작 위치
        y_offset = 10  # UI 요소들의 y 시작 위치
        line_height = 30 # 각 줄의 높이 (여백 포함)
        
        # 1. 시간 표시
        remaining_time = max(0, GAME_TIME_LIMIT - (time.time() - self.start_time))
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)
        time_text = self.font.render(f"시간: {minutes:02d}:{seconds:02d}", True, WHITE)
        self.screen.blit(time_text, (x_padding, y_offset))
        y_offset += line_height # 다음 UI를 위해 y_offset 증가

        # 2. 수집한 별 개수
        stars_text = self.font.render(f"별: {self.player.stars_collected}/5", True, WHITE)
        self.screen.blit(stars_text, (x_padding, y_offset))
        y_offset += line_height

        # 3. 은신 충전량
        stealth_charges_text = self.font.render(f"은신: {self.player.stealth_charges}", True, WHITE)
        self.screen.blit(stealth_charges_text, (x_padding, y_offset))
        y_offset += line_height

        # 4. 미니맵 활성화 상태 표시
        if time.time() < self.minimap_active_until:
            minimap_remaining_time = max(0, self.minimap_active_until - time.time())
            minimap_text = self.font.render(f"미니맵: {minimap_remaining_time:.1f}초", True, MINIMAP_ITEM_COLOR)
            self.screen.blit(minimap_text, (x_padding, y_offset))
        else:
            minimap_text = self.font.render("미니맵: 비활성", True, WHITE)
            self.screen.blit(minimap_text, (x_padding, y_offset))
        y_offset += line_height

        # 5. 이벤트 상태 표시 (조건부 렌더링)
        if self.current_event:
            event_name = ""
            event_color = WHITE
            if self.current_event == EventType.INVINCIBLE:
                event_name = "무적"
                event_color = (255, 255, 0)
            elif self.current_event == EventType.WALL_PASS:
                event_name = "벽 통과"
                event_color = (100, 255, 100)
            elif self.current_event == EventType.MAP_DARK:
                event_name = "맵 어두움"
                event_color = (150, 150, 150)
            elif self.current_event == EventType.ENEMY_SPEED_UP:
                event_name = "적 속도 UP"
                event_color = (255, 100, 100)
            
            event_remaining_time = max(0, self.event_active_until - time.time())
            event_text = self.font.render(f"이벤트: {event_name} {event_remaining_time:.1f}초", True, event_color)
            self.screen.blit(event_text, (x_padding, y_offset))
            y_offset += line_height # 이벤트가 표시되었을 때만 y_offset 증가
        else:
            # 이벤트가 없을 때는 공간을 차지하지 않도록 y_offset을 증가시키지 않음
            event_text = self.font.render("이벤트: 없음", True, WHITE)
            self.screen.blit(event_text, (x_padding, y_offset))
            y_offset += line_height

        # 6. AI 근접 경고 기능 (조건부 렌더링)
        min_ai_dist_sq = float('inf')
        for ai in self.ais:
            dx = ai.pos.x - self.player.pos.x
            dy = ai.pos.y - self.player.pos.y
            dist_sq = dx*dx + dy*dy
            if dist_sq < min_ai_dist_sq: 
                min_ai_dist_sq = dist_sq
        
        warning_color = None
        if min_ai_dist_sq <= 16:
            warning_color = WARNING_RED
        elif min_ai_dist_sq <= 49:
            warning_color = WARNING_YELLOW

        if warning_color:
            # 경고 아이콘 (삼각형)
            icon_points = [
                (x_padding + 10, y_offset + 5),
                (x_padding,      y_offset + 20),
                (x_padding + 20, y_offset + 20)
            ]
            pygame.draw.polygon(self.screen, warning_color, icon_points)
            
            # 경고 텍스트
            text = self.font.render("AI 근접 경고!", True, warning_color)
            self.screen.blit(text, (x_padding + 30, y_offset + 3)) # 아이콘 옆에 텍스트 배치
            y_offset += line_height # 경고가 표시되었을 때만 y_offset 증가

        # 7. 별 방향 표시 (섹션 제목 추가)
        y_offset += 10 # 섹션 간격
        section_title_text = self.font.render("남은 별 방향:", True, WHITE)
        self.screen.blit(section_title_text, (x_padding, y_offset))
        y_offset += line_height

        directions = self.get_star_directions()
        for i, direction in enumerate(directions):
            # 글자 크기를 small_font로 변경하여 공간 확보
            direction_text = self.small_font.render(f"별 {i+1}: {direction}", True, STAR_COLOR)
            self.screen.blit(direction_text, (x_padding + 10, y_offset)) # 들여쓰기
            y_offset += 25 # 작은 폰트에 맞게 줄 간격 조정

        # 8. 컨트롤 설명 (화면 아래쪽에 고정)
        controls = [
            "조작법:",
            "WASD/화살표: 이동",
            "Shift: 스프린트",
            "Space: 은신",
            "",
            "목표:",
            "별 5개 수집 후",
            "초록색 탈출구로!"
        ]
        
        # 이 부분은 화면 하단에 고정되므로 별도의 y 좌표 사용
        control_y_offset = SCREEN_HEIGHT - len(controls) * 20 - 10
        for control in controls:
            control_text = self.small_font.render(control, True, WHITE) # 작은 폰트 사용
            self.screen.blit(control_text, (x_padding, control_y_offset))
            control_y_offset += 20

    def draw_game_over(self):
        """게임 오버 화면"""
        overlay = pygame.Surface((SCREEN_WIDTH_WITH_UI, SCREEN_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        if self.state == GameState.WON:
            title = "승리!"
            subtitle = "별을 모두 모아 탈출했습니다!"
            color = (0, 255, 0)
        else:
            title = "패배!"
            subtitle = "다시 도전해보세요!"
            color = (255, 0, 0)
        
        title_text = self.large_font.render(title, True, color)
        subtitle_text = self.font.render(subtitle, True, WHITE)
        restart_text = self.font.render("R키를 눌러 다시 시작", True, WHITE)
        
        title_rect = title_text.get_rect(center=(SCREEN_WIDTH_WITH_UI//2, SCREEN_HEIGHT//2 - 50))
        subtitle_rect = subtitle_text.get_rect(center=(SCREEN_WIDTH_WITH_UI//2, SCREEN_HEIGHT//2))
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH_WITH_UI//2, SCREEN_HEIGHT//2 + 50))
        
        self.screen.blit(title_text, title_rect)
        self.screen.blit(subtitle_text, subtitle_rect)
        self.screen.blit(restart_text, restart_rect)
    
    def draw_menu(self):
        """메인 메뉴"""
        self.screen.fill(BLACK)
        
        # 타이틀
        title_text = self.large_font.render("Star Maze", True, WHITE)
        
        title_rect = title_text.get_rect(center=(SCREEN_WIDTH_WITH_UI//2, SCREEN_HEIGHT//2 - 200)) # 상단으로 이동
        
        self.screen.blit(title_text, title_rect)

        # --- AI 설명 추가 ---
        ai_descriptions = [
            ("AI 타입:", WHITE),
            (" ", WHITE), # 간격
            (f"  - 순찰 AI :", PATROL_AI_COLOR),
            ("    정해진 경로를 순찰하며, 플레이어 발견 시 추적합니다.", WHITE),
            (" ", WHITE), # 간격
            (f"  - 탐지 AI :", DETECTOR_AI_COLOR),
            ("    플레이어를 탐지하는 범위가 더 넓습니다.", WHITE),
            ("    플레이어를 놓치면 마지막 위치를 수색합니다.", WHITE),
            (" ", WHITE), # 간격
            (f"  - 강화 AI :", ENHANCED_AI_COLOR),
            ("    플레이어의 움직임을 미리 예측합니다.", WHITE),
            ("    (별 3개 획득 시 등장)", WHITE),
        ]
        
        y_offset = SCREEN_HEIGHT//2 - 175 # AI 설명 시작 Y 위치 조정
        for line, color in ai_descriptions:
            desc_text = self.font.render(line, True, color)
            self.screen.blit(desc_text, (SCREEN_WIDTH_WITH_UI//2 - desc_text.get_width()//2, y_offset))
            y_offset += 25 # 각 줄 간격

        # 시작 메시지
        start_text = self.large_font.render("Enter키를 눌러 시작", True, WHITE) # 시작 메시지 폰트 크기 변경
        start_rect = start_text.get_rect(center=(SCREEN_WIDTH_WITH_UI//2, SCREEN_HEIGHT//2 + 200)) # 하단으로 이동
        
        self.screen.blit(start_text, start_rect)
    
    async def run(self):
        """메인 게임 루프"""
        running = True
        
        while running:
            # handle_events()가 False를 반환하면 루프 종료
            if not self.handle_events():
                running = False
                break
            
            if self.state == GameState.PLAYING:
                self.handle_input()
                self.update()

            # 화면 그리기
            self.screen.fill(BLACK)
            
            if self.state == GameState.MENU:
                self.draw_menu()
            elif self.state == GameState.PLAYING:
                self.draw_maze()
                self.draw_entities()
                self.draw_ui()
                self.draw_game_messages()
            elif self.state in [GameState.WON, GameState.LOST]:
                # 게임 오버/승리 시에도 배경은 계속 그리도록 순서 조정
                self.draw_maze()
                self.draw_entities()
                self.draw_ui()
                self.draw_game_messages()
                self.draw_game_over()
            
            pygame.display.flip()
            # 웹 환경에서 브라우저가 멈추지 않도록 제어권을 넘겨줍니다.
            await asyncio.sleep(0)
        
        pygame.quit()

async def main():
    game = StarMazeGame()
    await game.run()

if __name__ == "__main__":
    asyncio.run(main())

