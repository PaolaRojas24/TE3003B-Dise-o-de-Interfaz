"""
Código que realiza la captura de fotos de cada objeto:

- Toma las fotos cuando se oprime la teca SPACE

- Cada objeto tiene su propia carpeta

- Se guardan con el nombre del objeto y con el numero de foto

Alumna: Ana Itzel Hernández García
"""
import cv2
import os

objeto = input("Nombre del objeto: ").strip()

# Carpeta de destino
carpeta = f"./{objeto}"
if not os.path.exists(carpeta):
    os.makedirs(carpeta)

# Inicializar cámara
cap = cv2.VideoCapture("http://10.50.88.149:4747/video")
if not cap.isOpened():
    print("No se pudo acceder a la cámara.")
    exit()

contador = len(os.listdir(carpeta)) + 1

print("Cámara iniciada.")
print("Presiona ESPACIO para capturar una imagen.")
print("Presiona ESC para salir.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error al capturar el frame.")
        break

    cv2.imshow("Presiona ESPACIO para capturar", frame)
    key = cv2.waitKey(1)

    if key == 27:  # ESC
        print("Saliendo...")
        break
    elif key == 32:  # ESPACIO
        filename = f"{objeto}-{contador}.jpg"
        path = os.path.join(carpeta, filename)
        success = cv2.imwrite(path, frame)
        if success:
            print(f"Imagen guardada: {path}")
            contador += 1
        else:
            print(f"Error al guardar la imagen en {path}")

cap.release()
cv2.destroyAllWindows()