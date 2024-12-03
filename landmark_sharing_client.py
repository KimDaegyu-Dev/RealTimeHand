import sys
import cv2
import numpy as np
import mediapipe as mp
import socketio
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLineEdit, QListWidget
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from PyQt5.QtCore import QTimer, Qt, QRectF

class LandmarkVisualizerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Landmark Visualizer')
        self.setGeometry(100, 100, 800, 600)
        self.landmarks = []
        self.received_landmarks = []
        self.winner = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw own landmarks (mirrored)
        self.draw_landmarks(painter, self.landmarks, Qt.green)

        # Draw received landmarks
        self.draw_landmarks(painter, self.received_landmarks, Qt.blue)

        # Draw winner text if applicable
        if self.winner:
            painter.setFont(QFont('Arial', 20))
            painter.setPen(Qt.red)
            if self.winner == 'self':
                text_rect = QRectF(10, self.height() - 40, self.width() - 20, 30)
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignBottom, "You won!")
            elif self.winner == 'opponent':
                text_rect = QRectF(10, 10, self.width() - 20, 30)
                painter.drawText(text_rect, Qt.AlignRight | Qt.AlignTop, "Opponent won!")

    def draw_landmarks(self, painter, landmarks, color):
        if not landmarks:
            return

        pen = QPen(color, 2)
        painter.setPen(pen)

        for landmark in landmarks:
            x, y = int(landmark['x'] * self.width()), int(landmark['y'] * self.height())
            painter.drawEllipse(x - 5, y - 5, 10, 10)

        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),  # Index finger
            (0, 9), (9, 10), (10, 11), (11, 12),  # Middle finger
            (0, 13), (13, 14), (14, 15), (15, 16),  # Ring finger
            (0, 17), (17, 18), (18, 19), (19, 20)  # Pinky
        ]

        for connection in connections:
            start_point = (int(landmarks[connection[0]]['x'] * self.width()),
                           int(landmarks[connection[0]]['y'] * self.height()))
            end_point = (int(landmarks[connection[1]]['x'] * self.width()),
                         int(landmarks[connection[1]]['y'] * self.height()))
            painter.drawLine(start_point[0], start_point[1], end_point[0], end_point[1])

    def update_landmarks(self, landmarks, received=False):
        if received:
            self.received_landmarks = landmarks
        else:
            self.landmarks = landmarks
        self.update()

    def set_winner(self, winner):
        self.winner = winner
        self.update()

class LandmarkSharingApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
        self.sio = socketio.Client()
        self.setup_socket_events()
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1)
        
        self.cap = cv2.VideoCapture(0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(10)  # Update every 10ms
        
        self.selected_user = None
        self.landmark_visualizer = LandmarkVisualizerWindow()
        self.landmark_visualizer.show()

    def initUI(self):
        layout = QVBoxLayout()
        
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Enter your username")
        layout.addWidget(self.username_input)
        
        self.connect_button = QPushButton('Connect', self)
        self.connect_button.clicked.connect(self.connect_to_server)
        layout.addWidget(self.connect_button)
        
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
            self.check_winner(data['landmarks'] if data['landmarks'] else None)

    def connect_to_server(self):
        username = self.username_input.text()
        if username:
            self.sio.connect('http://3.34.70.33:3000')
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
            hand_landmarks = results.multi_hand_landmarks[0]
            landmarks_list = [
                {"x": 1 - lm.x, "y": lm.y, "z": lm.z}  # Mirror the x-coordinate
                for lm in hand_landmarks.landmark
            ]
            
            self.landmark_visualizer.update_landmarks(landmarks_list)
            
            if self.selected_user:
                self.sio.emit('landmarks', {'targetUser': self.selected_user, 'landmarks': landmarks_list})

    def check_winner(self, opponent_landmarks):
        if not self.landmarks or not opponent_landmarks:
            return

        own_gesture = self.recognize_gesture(self.landmarks)
        opponent_gesture = self.recognize_gesture(opponent_landmarks)

        if own_gesture and opponent_gesture:
            if own_gesture == opponent_gesture:
                self.landmark_visualizer.set_winner(None)
            elif (
                (own_gesture == 'rock' and opponent_gesture == 'scissors') or
                (own_gesture == 'paper' and opponent_gesture == 'rock') or
                (own_gesture == 'scissors' and opponent_gesture == 'paper')
            ):
                self.landmark_visualizer.set_winner('self')
            else:
                self.landmark_visualizer.set_winner('opponent')

    def recognize_gesture(self, landmarks):
        # Implement rock-paper-scissors gesture recognition
        # This is a simplified version and may need refinement
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]

        if (thumb_tip['y'] < index_tip['y'] and
            index_tip['y'] < middle_tip['y'] and
            middle_tip['y'] < ring_tip['y'] and
            ring_tip['y'] < pinky_tip['y']):
            return 'rock'
        elif (thumb_tip['y'] > index_tip['y'] and
              thumb_tip['y'] > middle_tip['y'] and
              thumb_tip['y'] > ring_tip['y'] and
              thumb_tip['y'] > pinky_tip['y']):
            return 'paper'
        elif (index_tip['y'] < ring_tip['y'] and
              middle_tip['y'] < ring_tip['y'] and
              pinky_tip['y'] > ring_tip['y']):
            return 'scissors'
        return None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = LandmarkSharingApp()
    sys.exit(app.exec_())

