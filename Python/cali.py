"""
import cv2, glob
fotos = glob.glob('./chess/*.jpg')
print(fotos)  # primero verifica que las encuentra
img = cv2.imread(fotos[0])
print(img.shape)
"""
import cv2 as cv
import numpy as np
import glob
import yaml

# ── Configuración ─────────────────────────────────────────────
ChessGrid  = (6, 4)       # esquinas internas = cuadros - 1
TAM_CUADRO = 40.0         # mm (4 cm)
framesize  = (1280, 720)

CARPETA    = './chess/*.jpg'
ARCHIVO    = 'NuevaCalibracion.yaml'
# ──────────────────────────────────────────────────────────────

criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)

objp = np.zeros((ChessGrid[0] * ChessGrid[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:ChessGrid[0], 0:ChessGrid[1]].T.reshape(-1, 2) * TAM_CUADRO

objpoints = []
imgpoints = []

images = glob.glob(CARPETA)
print(f"Imágenes encontradas: {len(images)}")

for fname in images:
    img  = cv.imread(fname)
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

    found, corners = cv.findChessboardCorners(gray, ChessGrid, None)
    print(f"  {fname}  ->  {'OK' if found else 'no encontrado'}")

    if found:
        corners2 = cv.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        objpoints.append(objp)
        imgpoints.append(corners2)

        cv.drawChessboardCorners(img, ChessGrid, corners2, found)
        cv.imshow('Tablero', img)
        cv.waitKey(300)

cv.destroyAllWindows()

if len(objpoints) < 3:
    print("Pocas imágenes válidas, verifica la carpeta o el tamaño del tablero.")
    exit()

# ── Calibración ───────────────────────────────────────────────
ret, cameraMatrix, dist, rvecs, tvecs = cv.calibrateCamera(
    objpoints, imgpoints, framesize, None, None
)

# Error de reproyección
error_total = 0
for i in range(len(objpoints)):
    p2d, _ = cv.projectPoints(objpoints[i], rvecs[i], tvecs[i], cameraMatrix, dist)
    error_total += cv.norm(imgpoints[i], p2d, cv.NORM_L2) / len(p2d)
error_medio = error_total / len(objpoints)

print(f"\n=== RESULTADO ===")
print(f"Imágenes usadas : {len(objpoints)}")
print(f"fx={cameraMatrix[0,0]:.2f}  fy={cameraMatrix[1,1]:.2f}")
print(f"cx={cameraMatrix[0,2]:.2f}  cy={cameraMatrix[1,2]:.2f}")
print(f"Distorsión      : {dist.ravel()}")
print(f"Error reproyección: {error_medio:.4f} px  ", end="")
print("(BUENA ✓)" if error_medio < 0.5 else "(ACEPTABLE)" if error_medio < 1.0 else "(MALA — repite)")

# ── Guardar YAML ──────────────────────────────────────────────
data = {
    'cameraMatrix': cameraMatrix.tolist(),
    'dist':         dist.tolist(),
    'rvecs':        np.array(rvecs).tolist(),
    'tvecs':        np.array(tvecs).tolist(),
}
with open(ARCHIVO, 'w') as f:
    yaml.dump(data, f)
print(f"\nGuardado en '{ARCHIVO}'")

# ── Verificar lectura ─────────────────────────────────────────
with open(ARCHIVO, 'r') as f:
    loaded = yaml.safe_load(f)

K    = np.array(loaded['cameraMatrix'])
dist = np.array(loaded['dist'])
print(f"\nMatriz K cargada:\n{K}")
