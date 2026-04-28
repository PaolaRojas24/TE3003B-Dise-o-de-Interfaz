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


def detectar_figura(frame):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 50, 150)
    contornos, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    mejor, mayor_area = None, 0

    for cnt in contornos:
        area = cv2.contourArea(cnt)
        if area < 1000:
            continue

        peri   = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        x, y, w, h = cv2.boundingRect(approx)
        nv = len(approx)

        figura = ""
        if nv == 3:
            figura = "Triangulo"
        elif nv == 4:
            figura = "Cuadrado" if 0.85 <= float(w) / h <= 1.15 else "Rectangulo"
        else:
            if (4 * np.pi * area) / (peri ** 2) > 0.75:
                figura = "Circulo"

        if figura and area > mayor_area:
            mayor_area = area
            mejor = {
                "figura":   figura,
                "cx":       x + w // 2,
                "cy":       y + h // 2,   # ← fix: era w // 2
                "contorno": approx
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
print("'s' = enviar robot a figura  |  'q' = salir")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Sin señal de cámara")
        break

    #frame = cv2.flip(frame, 1)
    det   = detectar_figura(frame)

    if det:
        cx, cy = det["cx"], det["cy"]
        cv2.drawContours(frame, [det["contorno"]], -1, (0, 255, 0), 2)
        cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)
        cv2.putText(frame, det["figura"], (cx - 40, cy - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        pos = pixel_a_robot(cx, cy)
        cv2.putText(frame, f"Robot: ({pos[0]:.0f}, {pos[1]:.0f}) mm", (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 0), 2)

    # imshow y waitKey siempre fuera del if
    cv2.imshow("Vision Robot", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('s') and det:
        pos = pixel_a_robot(det["cx"], det["cy"])
        code, current = arm.get_position()
        x_act, y_act, z_act, roll, pitch, yaw = current
        print(f"\n--- DEBUG ---")
        print(f"  Figura       : {det['figura']}")
        print(f"  Pixel        : cx={det['cx']}  cy={det['cy']}")
        print(f"  Pos actual   : x={x_act:.1f}  y={y_act:.1f}  z={z_act:.1f}")
        print(f"  Pos calculada: x={pos[0]:.1f}  y={pos[1]:.1f}  z={pos[2]:.1f}")
        print(f"  Moverá z a   : {z_trabajo}")
        print(f"-------------")
        confirm = input("¿Mover? (s/n): ").strip().lower()
        if confirm == 's':
            arm.set_position(x=pos[0], y=pos[1], z=z_trabajo,
                             roll=roll, pitch=pitch, yaw=yaw,
                             speed=speed, mvacc=mvacc, wait=True)
            print("Listo.")

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
arm.disconnect()