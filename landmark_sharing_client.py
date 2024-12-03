import sys
import cv2
import numpy as np
import mediapipe as mp
import socketio
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QListWidget
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush
from PyQt5.QtCore import QTimer, Qt, QRectF, QPointF

class Particle:
    def __init__(self, x, y):
        self.pos = QPointF(x, y)
        self.velocity = QPointF(np.random.uniform(-1, 1), np.random.uniform(-1, 1))
        self.life = 1.0
        self.color = QColor(255, 255, 255)

    def update(self):
        self.pos += self.velocity
        self.life -= 0.2
        self.color.setAlphaF(self.life)

class LandmarkVisualizerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Landmark Visualizer')
        self.setGeometry(100, 100, 800, 600)
        self.landmarks = {'Left': [], 'Right': []}
        self.received_landmarks = []
        self.particles = []

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw own landmarks
        self.draw_landmarks(painter, self.landmarks['Left'], Qt.green)
        self.draw_landmarks(painter, self.landmarks['Right'], Qt.green)

        # Draw received landmarks
        self.draw_landmarks(painter, self.received_landmarks, Qt.blue)

        # Draw particles
        for particle in self.particles:
            painter.setBrush(QBrush(particle.color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(particle.pos, 3, 3)

    def draw_landmarks(self, painter, landmarks, color):
        if not landmarks:
            return

        pen = QPen(color, 2)
        painter.setPen(pen)

        for landmark in landmarks:
            x, y = int((1 - landmark['x']) * self.width()), int(landmark['y'] * self.height())
            painter.drawEllipse(x - 5, y - 5, 10, 10)

            # Check for collision with received landmarks
            for received_landmark in self.received_landmarks:
                rx, ry = int((1 - received_landmark['x']) * self.width()), int(received_landmark['y'] * self.height())
                if abs(x - rx) < 10 and abs(y - ry) < 10:
                    self.create_particles(x, y)

        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),  # Index finger
            (0, 9), (9, 10), (10, 11), (11, 12),  # Middle finger
            (0, 13), (13, 14), (14, 15), (15, 16),  # Ring finger
            (0, 17), (17, 18), (18, 19), (19, 20)  # Pinky
        ]

        for connection in connections:
            start_point = (int((1 - landmarks[connection[0]]['x']) * self.width()),
                           int(landmarks[connection[0]]['y'] * self.height()))
            end_point = (int((1 - landmarks[connection[1]]['x']) * self.width()),
                         int(landmarks[connection[1]]['y'] * self.height()))
            painter.drawLine(start_point[0], start_point[1], end_point[0], end_point[1])

    def create_particles(self, x, y):
        for _ in range(10):
            self.particles.append(Particle(x, y))

    def update_particles(self):
        self.particles = [p for p in self.particles if p.life > 0]
        for particle in self.particles:
            particle.update()
        self.update()

    def update_landmarks(self, landmarks, hand_type='Left', received=False):
        if received:
            self.received_landmarks = landmarks
        else:
            self.landmarks[hand_type] = landmarks
        self.update()

class LandmarkSharingApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
        self.sio = socketio.Client()
        self.setup_socket_events()
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=2)
        
        self.cap = cv2.VideoCapture(0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(10)  # Update every 10ms
        
        self.selected_user = None
        self.landmark_visualizer = LandmarkVisualizerWindow()
        self.landmark_visualizer.show()

        # Timer for updating particles
        self.particle_timer = QTimer(self)
        self.particle_timer.timeout.connect(self.landmark_visualizer.update_particles)
        self.particle_timer.start(16)  # 60 FPS

    def initUI(self):
        layout = QVBoxLayout()
        
        # Username input
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Enter your username")
        layout.addWidget(self.username_input)
        
        self.connect_button = QPushButton('Connect', self)
        self.connect_button.clicked.connect(self.connect_to_server)
        layout.addWidget(self.connect_button)
        
        # User list
        self.user_list = QListWidget(self)
        self.user_list.itemClicked.connect(self.select_user)
        layout.addWidget(self.user_list)
        
        self.setLayout(layout)
        self.setWindowTitle('Landmark Sharing App')
        self.show()

    def setup_socket_events(self):
        @self.sio.event
        def connect():
            print('Connected to server')

        @self.sio.event
        def disconnect():
            print('Disconnected from server')

        @self.sio.on('userList')
        def on_user_list(users):
            self.user_list.clear()
            for user in users:
                if user != self.username_input.text():
                    self.user_list.addItem(user)

        @self.sio.on('landmarks')
        def on_landmarks(data):
            self.landmark_visualizer.update_landmarks(data['landmarks'], received=True)

    def connect_to_server(self):
        username = self.username_input.text()
        if username:
            self.sio.connect('http://localhost:3000')
            self.sio.emit('register', username)
            self.connect_button.setEnabled(False)
            self.username_input.setEnabled(False)

    def select_user(self, item):
        self.selected_user = item.text()

    def update_frame(self):
        success, image = self.cap.read()
        if not success:
            return

        image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
        results = self.hands.process(image)

        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                hand_type = handedness.classification[0].label
                landmarks_list = [
                    {"x": lm.x, "y": lm.y, "z": lm.z}
                    for lm in hand_landmarks.landmark
                ]
                
                self.landmark_visualizer.update_landmarks(landmarks_list, hand_type)
            
            if self.selected_user:
                self.sio.emit('landmarks', {'targetUser': self.selected_user, 'landmarks': landmarks_list})

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = LandmarkSharingApp()
    sys.exit(app.exec_())

