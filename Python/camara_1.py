import sys
import os
import cv2
import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
from xarm.wrapper import XArmAPI

# ── Configuración ─────────────────────────────────────────────
robot_ip  = "172.23.254.167"
cam_url   = 'http://10.50.88.149:4747/video'
speed     = 30
mvacc     = 200
z_trabajo = 150  # mm — altura final sobre la pieza

# Intrínsecos reales de la calibración
fx, fy         = 1078.65, 1077.06
cx_img, cy_img = 626.20, 253.81
h_cam          = 300.0  # distancia cámara → plano de trabajo (mm)
cy_horiz       = -392.4 # cy del horizonte (calculado con tilt=31°)

# Distorsión (de tu calibración)
dist = np.array([[ 7.31329515e-02,  8.23424300e-01, -1.44209467e-02,
                  -2.29809355e-03, -3.89945277e+00]])

# Transformación cámara fija → base robot
# Confirmado con setup físico:
#   +Xc (derecha imagen) → +Y robot
#   +Yc (abajo imagen)   → -Z robot
#   +Zc (profundidad)    → -X robot
R = np.array([[ 0,  0, -1],   # X_robot = -Zc
              [ 1,  0,  0],   # Y_robot = +Xc
              [ 0, -1,  0],   # Z_robot = -Yc
              ], dtype=float)
t = np.array([460.0 +132, 320.0-161, 250.0])  # mm: posición cámara en base robot

T_BASE_CAM = np.eye(4)
T_BASE_CAM[:3, :3] = R
T_BASE_CAM[:3,  3] = t
# ──────────────────────────────────────────────────────────────

def det_cuadrado(frame):

    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 50, 150)

    contornos, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mejor = None
    mayor_area = 0

    for contorno in contornos:
        area = cv2.contourArea(contorno)
        if area < 1000:
            continue

        perimetro = cv2.arcLength(contorno, True)
        approx    = cv2.approxPolyDP(contorno, 0.04 * perimetro, True)
        x, y, w, h = cv2.boundingRect(approx)

        figura = ""
        color  = (0, 255, 0)
        num_vertices = len(approx)

        if num_vertices == 4:
            aspect_ratio = float(w) / h
            figura = "Cuadrado" if 0.85 <= aspect_ratio <= 1.15 else "Rectangulo"
            color  = (0, 0, 255)


        if figura and area > mayor_area:
            mayor_area = area
            mejor = {
                "figura":   figura,
                "cx":       x + w // 2,
                "cy":       y + h // 2,   # ← fix: era w // 2
                "contorno": approx,
                "color": color
            }
    return mejor

def det_triangulo(frame):
    
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 50, 150)


    contornos, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mejor = None
    mayor_area = 0

    for contorno in contornos:
        area = cv2.contourArea(contorno)
        if area < 1000:
            continue

        perimetro = cv2.arcLength(contorno, True)
        approx    = cv2.approxPolyDP(contorno, 0.04 * perimetro, True)
        x, y, w, h = cv2.boundingRect(approx)
        

        figura = ""
        color  = (0, 255, 0)
        num_vertices = len(approx)

        if num_vertices == 3:
            figura = "Triangulo"
            color  = (0, 255, 255)


        if figura and area > mayor_area:
            mayor_area = area
            mejor = {
                "figura":   figura,
                "cx":       x + w // 2,
                "cy":       y + h // 2, 
                "contorno": approx,
                "color": color
            }
    return mejor


def det_circulo(frame):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 50, 150)
    

    contornos, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mejor = None
    mayor_area = 0

    for contorno in contornos:
        area = cv2.contourArea(contorno)
        if area < 1000:
            continue

        perimetro = cv2.arcLength(contorno, True)
        approx    = cv2.approxPolyDP(contorno, 0.04 * perimetro, True)
        x, y, w, h = cv2.boundingRect(approx)
        

        figura = ""
        color  = (0, 255, 0)
        num_vertices = len(approx)

        circularidad = (4 * np.pi * area) / (perimetro ** 2)
        if circularidad > 0.75:
            figura = "Circulo"
            color  = (255, 0, 0)


        if figura and area > mayor_area:
            mayor_area = area
            mejor = {
                "figura":   figura,
                "cx":       x + w // 2,
                "cy":       y + h // 2, 
                "contorno": approx,
                "color": color
            }
    return mejor


def pixel_a_robot(px, py):
    if py <= cy_horiz:
        py = cy_horiz + 1

    z_cam = h_cam * fy /(py - cy_horiz)
    Xc = (px - cx_img) * z_cam / fx
    Yc = (py - cy_img) * z_cam / fy
    P  = T_BASE_CAM @ np.array([Xc, Yc, z_cam, 1.0])
    return P[:3]


# ── Conectar robot ────────────────────────────────────────────
arm = XArmAPI(robot_ip)
arm.motion_enable(enable=True)
arm.set_mode(0)
arm.set_state(0)

# ── Abrir cámara ──────────────────────────────────────────────
cap = cv2.VideoCapture(cam_url)

SECUENCIA = [det_triangulo, det_cuadrado, det_circulo]
NOMBRES   = ["Triangulo",   "Cuadrado",   "Circulo"]
modo_auto           = True
idx_secuencia       = 0
frames_confirmacion = 0
FRAMES_REQUERIDOS   = 5

while True:
    ret, frame = cap.read()
    if not ret:
        print("Sin señal de cámara")
        break

    # Solo llamar la función que toca
    det = None
    if idx_secuencia < len(SECUENCIA):
        det = SECUENCIA[idx_secuencia](frame)

    if det:
        cv2.drawContours(frame, [det["contorno"]], -1, det["color"], 2)
        cv2.circle(frame, (det["cx"], det["cy"]), 6, (255, 255, 255), -1)
        cv2.putText(frame, det["figura"], (det["cx"] - 40, det["cy"] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, det["color"], 2)
        frames_confirmacion += 1
    else:
        frames_confirmacion = 0

    # Estado
    if idx_secuencia < len(SECUENCIA):
        cv2.putText(frame, f"Buscando: {NOMBRES[idx_secuencia]} ({idx_secuencia+1}/{len(SECUENCIA)})",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "Secuencia completa!", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imshow("Vision Robot", frame)
    key = cv2.waitKey(1) & 0xFF

    # Mover cuando hay suficientes frames confirmados
    if frames_confirmacion >= FRAMES_REQUERIDOS and idx_secuencia < len(SECUENCIA):
        frames_confirmacion = 0
        pos = pixel_a_robot(det["cx"], det["cy"])
        _, current = arm.get_position()
        _, _, _, roll, pitch, yaw = current
        print(f"\n→ Moviendo a {NOMBRES[idx_secuencia]}: x={pos[0]:.1f}, y={pos[1]:.1f}")
        arm.set_position(x=pos[0], y=pos[1], z=z_trabajo,
                         roll=roll, pitch=pitch, yaw=yaw,
                         speed=speed, mvacc=mvacc, wait=True)
        print(f"  Listo.")
        idx_secuencia += 1

    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
arm.disconnect()