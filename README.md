# 🌟 Star Maze - A* 알고리즘 기반 AI 게임

공학일반 심화탐구 활동의 일환으로 제작된 Pygame 기반 2D 미로 탈출 게임입니다. A* 알고리즘을 활용해 AI의 경로 탐색 능력을 지능적으로 향상시켰으며, `pygbag`을 통해 웹으로도 배포하여 누구나 게임을 즐길 수 있도록 했습니다.

**[▶ 게임 플레이 바로가기](https://sinsangwoo.github.io/STAR_MAZE/)**

---

## 🧩 프로젝트 개요

- 문제 인식: 단순한 추적 로직만으로는 AI가 장애물 회피나 경로 최적화를 수행하지 못함
- 해결 방법: A* 알고리즘을 도입해, AI가 미로의 구조를 고려한 최적 경로를 계산하고 플레이어를 추적
- 확장 목표: GitHub Pages를 활용해 웹에서 누구나 플레이 가능한 상태로 배포

---

## 🛠️ 기술 스택

| 분야         | 기술                             |
|--------------|----------------------------------|
| 언어         | Python 3                         |
| 게임 엔진    | Pygame                           |
| 경로 탐색    | A* 알고리즘 (Manhattan 거리 기반) |
| 자료구조     | heapq (우선순위 큐), set         |
| 웹 배포      | pygbag (WASM 변환), GitHub Pages |

---

## ⚙️ 주요 기능 및 시스템

### 🔍 A* 기반 AI 시스템

- 벽을 우회하고 플레이어를 추적하는 지능형 적 AI 구현
- Open 리스트는 `heapq`로, Closed 리스트는 `set`으로 구성
- 플레이어가 3개 이상의 별을 수집하면 고급 AI 등장

---

### 🌐 웹 배포

- `pygbag`을 사용하여 Python 코드를 WebAssembly로 변환
- 비동기 루프(`asyncio`)를 도입하여 브라우저 멈춤 현상 해결
- 한글 폰트 깨짐 문제 해결을 위해 `.ttf` 폰트 파일 직접 포함

---

## 💻 설치 및 실행 방법

### ▶ 데스크탑(Python) 버전 실행

```bash
git clone https://github.com/sinsangwoo/STAR_MAZE.git
cd STAR_MAZE
python -m venv venv
source venv/bin/activate  # 또는 .\venv\Scripts\activate (Windows)
pip install pygame
python main.py

📚 프로젝트에서 배운 점
이론적으로 배운 A* 알고리즘을 실제 코드에 적용하는 경험

데스크탑 앱과 웹 앱의 구조적 차이 및 디버깅 경험

GitHub Pages와 pygbag을 활용한 실질적인 배포 경험

협업과 공유를 위한 오픈소스 마인드 함양

🎓 교육 활용 및 추천
이 프로젝트는 다음과 같은 상황에서 유용하게 사용될 수 있습니다:

고등학생/대학생을 위한 알고리즘 실습 예제

컴퓨터과학 교과의 A 알고리즘 시각화 프로젝트*

웹 배포 경험을 쌓고 싶은 Pygame 사용자

공학일반, 정보, 프로그래밍 과목의 심화탐구 주제

