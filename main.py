import sys
import os
import ctypes
import shutil
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QPixmap, QPainter, QColor, QCursor, QIcon
from PyQt6.QtCore import Qt, QTimer

class CursorPet(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 1. 윈도우 설정: 테두리 없음, 항상 최상단, 배경 투명, 클릭 관통
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.label = QLabel(self)
        
        self.current_screen = QApplication.primaryScreen()
        
        # 사용자가 지정할 배율 (기본 1.0 = 100%)
        self.user_scale = 1.0
        
        # 마우스와 캐릭터 사이의 거리(Offset) 설정 (기본 10)
        self.user_offset = 10
        
        # 2. 캐릭터 폴더 확인 및 생성
        self.char_dir = "characters"
        if getattr(sys, 'frozen', False):
            # exe로 실행된 경우, exe 파일이 있는 곳의 characters 폴더 사용
            self.char_dir = os.path.join(os.path.dirname(sys.executable), "characters")
            
        if not os.path.exists(self.char_dir):
            try:
                os.makedirs(self.char_dir)
            except Exception:
                pass
                
        # PyInstaller 빌드 시 내장된 기본 캐릭터들을 외부 폴더로 복사 (최초 실행 시 또는 파일이 없을 때)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            bundled_char_dir = os.path.join(sys._MEIPASS, "characters")
            if os.path.exists(bundled_char_dir):
                for item in os.listdir(bundled_char_dir):
                    s = os.path.join(bundled_char_dir, item)
                    d = os.path.join(self.char_dir, item)
                    if not os.path.exists(d):
                        try:
                            if os.path.isdir(s):
                                shutil.copytree(s, d)
                            else:
                                shutil.copy2(s, d)
                        except Exception:
                            pass
                            
        # 초기 캐릭터 로드 (폴더에 이미지가 있으면 첫 번째 이미지 로드, 없으면 기본 동그라미)
        self.load_initial_character()

        # 4. 타이머 설정 (마우스 추적)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_position)
        self.timer.start(16)

        # 5. 시스템 트레이 설정
        self.tray_icon = QSystemTrayIcon(self)
        self.update_tray_icon()
        self.create_tray_menu()
        self.tray_icon.show()

    def load_initial_character(self):
        images = [f for f in os.listdir(self.char_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        if images:
            self.load_character(os.path.join(self.char_dir, images[0]))
        else:
            self.load_default_character()

    def load_character(self, filepath):
        try:
            pixmap = QPixmap(filepath)
            if pixmap.isNull():
                raise Exception("이미지를 불러올 수 없습니다.")
            self.original_pixmap = pixmap
            self.apply_character_scale()
        except Exception as e:
            print(f"이미지 로드 실패 ({filepath}): {e}")
            self.load_default_character()

    def load_default_character(self):
        self.original_pixmap = self.create_default_character()
        self.apply_character_scale()

    def apply_character_scale(self):
        if not hasattr(self, 'original_pixmap') or self.original_pixmap.isNull():
            return
            
        screen_height = self.current_screen.geometry().height() if self.current_screen else 1080
        
        # 1920x1080 (FHD) 기준 기본 크기를 80으로 설정하고, 해상도에 비례하게 크기 조절
        # 그리고 사용자가 설정한 배율(user_scale)을 추가로 곱해줍니다.
        target_size = int(80 * (screen_height / 1080.0) * self.user_scale)
        target_size = max(20, min(target_size, 800)) # 최소 20, 최대 800 픽셀로 한계 확장

        # 원본 비율을 유지(KeepAspectRatio)하면서 지정된 박스 안에 들어가도록 스케일링
        scaled_pixmap = self.original_pixmap.scaled(
            target_size, target_size, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.label.setPixmap(scaled_pixmap)
        self.label.resize(scaled_pixmap.width(), scaled_pixmap.height())
        self.resize(scaled_pixmap.width(), scaled_pixmap.height())
        
        if hasattr(self, 'tray_icon'):
            self.update_tray_icon()

    def update_tray_icon(self):
        if not self.label.pixmap().isNull():
            self.tray_icon.setIcon(QIcon(self.label.pixmap()))
        self.tray_icon.setToolTip("CursorPet - 우클릭하여 메뉴를 열어보세요.")

    def create_tray_menu(self):
        self.tray_menu = QMenu()
        
        # 캐릭터 변경 서브메뉴
        self.char_menu = self.tray_menu.addMenu("캐릭터 변경")
        
        # 크기 조절 서브메뉴
        self.scale_menu = self.tray_menu.addMenu("크기 조절")
        scales = [("50% (매우 작게)", 0.5), ("75% (작게)", 0.75), ("100% (기본)", 1.0), 
                  ("125% (조금 크게)", 1.25), ("150% (크게)", 1.5), ("200% (매우 크게)", 2.0),
                  ("300% (거대하게)", 3.0)]
        for text, value in scales:
            action = self.scale_menu.addAction(text)
            action.triggered.connect(lambda checked, v=value: self.set_scale(v))
            
        # 거리 조절 (마우스와의 간격) 서브메뉴
        self.offset_menu = self.tray_menu.addMenu("마우스와의 거리 조절")
        offsets = [("겹치게 (-20px)", -20), 
                   ("바짝 붙이기 (0px)", 0), 
                   ("가깝게 (10px) - 기본", 10), 
                   ("약간 멀리 (20px)", 20), 
                   ("멀리 (40px)", 40), 
                   ("매우 멀리 (80px)", 80)]
        for text, value in offsets:
            action = self.offset_menu.addAction(text)
            action.triggered.connect(lambda checked, v=value: self.set_offset(v))
        
        # 폴더 새로고침 메뉴 (새로운 이미지를 폴더에 넣었을 때 메뉴에 즉시 반영)
        refresh_action = self.tray_menu.addAction("새로고침 (이미지 스캔)")
        refresh_action.triggered.connect(self.update_char_menu)
        
        self.tray_menu.addSeparator()
        
        # 종료 메뉴
        quit_action = self.tray_menu.addAction("종료 (Quit)")
        quit_action.triggered.connect(QApplication.instance().quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.update_char_menu()

    def update_char_menu(self):
        self.char_menu.clear()
        
        # 기본 캐릭터(동그라미) 추가
        default_action = self.char_menu.addAction("기본 캐릭터 (동그라미)")
        default_action.triggered.connect(self.load_default_character)
        self.char_menu.addSeparator()
        
        # characters 폴더 스캔
        images = [f for f in os.listdir(self.char_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        
        for img in images:
            filepath = os.path.join(self.char_dir, img)
            # 람다 함수에서 기본 인자를 사용하여 현재 filepath 값을 고정
            action = self.char_menu.addAction(img)
            action.triggered.connect(lambda checked, path=filepath: self.load_character(path))

    def set_scale(self, value):
        self.user_scale = value
        self.apply_character_scale()

    def set_offset(self, value):
        self.user_offset = value

    def create_default_character(self):
        # 넉넉한 크기(500x500)로 원본 캔버스를 그려두면, 4K 등에서 커져도 깨지지 않습니다.
        base_size = 500
        pixmap = QPixmap(base_size, base_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        scale = base_size / 100.0
        
        # 얼굴 (노란색)
        painter.setBrush(QColor(255, 215, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(10*scale), int(10*scale), int(80*scale), int(80*scale))

        # 눈 (검은색)
        painter.setBrush(QColor(0, 0, 0))
        painter.drawEllipse(int(30*scale), int(35*scale), int(10*scale), int(10*scale))
        painter.drawEllipse(int(60*scale), int(35*scale), int(10*scale), int(10*scale))

        # 입 (빨간색)
        painter.setBrush(QColor(255, 100, 100))
        painter.drawEllipse(int(40*scale), int(60*scale), int(20*scale), int(10*scale))
        
        painter.end()
        return pixmap

    def update_position(self):
        # 현재 마우스 위치 가져오기
        pos = QCursor.pos()
        
        # 모니터(화면)가 변경되었는지 확인하여 크기 재조정
        current_screen = QApplication.screenAt(pos)
        if current_screen and current_screen != self.current_screen:
            self.current_screen = current_screen
            self.apply_character_scale()
            
        offset_x = self.user_offset
        offset_y = self.user_offset
        self.move(pos.x() + offset_x, pos.y() + offset_y)
        
        # 강제 최상단 유지 (다른 창이나 웹브라우저 뒤로 숨는 현상 방지)
        self.raise_()
        try:
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass

if __name__ == '__main__':
    # 다중 모니터 해상도/배율 다름으로 인한 깜빡임, 크기 변동, 좌표 튐 현상 방지
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    
    app = QApplication(sys.argv)
    pet = CursorPet()
    pet.show()
    sys.exit(app.exec())
