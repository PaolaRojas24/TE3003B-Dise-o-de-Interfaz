# main.py
import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from interfaz import Ui_MainWindow

sys.path.append(os.path.join(os.path.dirname(__file__),
                '../xArm-Python-SDK/example/wrapper/common'))
from dibujo import HiloDibujo


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ruta_gnc = None
        self.hilo     = None

        # ── Navegación del menú ──────────────────────────────────────
        self.ui.bt_control.clicked.connect(lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.p_control))
        self.ui.bt_camara.clicked.connect( lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.p_camara))
        self.ui.bt_dIbujo.clicked.connect( lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.p_dibujo))
        self.ui.bt_trazo.clicked.connect(  lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.p_trazo))

        # ── Página Dibujo ────────────────────────────────────────────
        self.ui.bt_cargar.clicked.connect(self.cargar_archivo)
        self.ui.bt_iniciar.clicked.connect(self.conectar_robot)
        self.ui.bt_bajar.clicked.connect(self.bajar_lapiz)
        self.ui.bt_confirmar.clicked.connect(self.confirmar_altura)

    # ── Cargar archivo .gnc ──────────────────────────────────────────
    def cargar_archivo(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo G-code", "", "GNC Files (*.gnc *.ngc);;All Files (*)"
        )
        if ruta:
            self.ruta_gnc = ruta
            nombre = ruta.split("/")[-1]
            self.ui.lbl_archivo.setText(f"✔ {nombre}")
            self.ui.bt_iniciar.setEnabled(True)

    # ── Conectar robot y llevarlo a posición base ────────────────────
    def conectar_robot(self):
        self.ui.bt_iniciar.setEnabled(False)
        self.ui.bt_cargar.setEnabled(False)
        self.ui.lbl_archivo.setText("⏳ Conectando robot...")

        self.hilo = HiloDibujo(self.ruta_gnc)
        self.hilo.listo_para_bajar.connect(self.mostrar_controles_altura)
        self.hilo.terminado.connect(self.dibujo_terminado)
        self.hilo.error.connect(self.dibujo_error)
        self.hilo.start()

    # ── Se activan cuando el robot ya está en posición base ──────────
    def mostrar_controles_altura(self):
        self.ui.bt_bajar.setEnabled(True)
        self.ui.bt_confirmar.setEnabled(True)
        self.ui.lbl_archivo.setText("⬇ Ajusta la altura del lápiz")

    # ── Bajar el lápiz 1mm ───────────────────────────────────────────
    def bajar_lapiz(self):
        if self.hilo:
            self.hilo.bajar_un_mm()

    # ── Confirmar altura y empezar a dibujar ─────────────────────────
    def confirmar_altura(self):
        if self.hilo:
            self.ui.bt_bajar.setEnabled(False)
            self.ui.bt_confirmar.setEnabled(False)
            self.ui.lbl_archivo.setText("⏳ Dibujando...")
            self.hilo.confirmar_inicio()

    # ── Dibujo terminado ─────────────────────────────────────────────
    def dibujo_terminado(self):
        self.ui.lbl_archivo.setText("✅ ¡Dibujo completado!")
        self.ui.bt_cargar.setEnabled(True)
        self.ui.bt_iniciar.setEnabled(True)

    # ── Error del robot ──────────────────────────────────────────────
    def dibujo_error(self, msg):
        self.ui.lbl_archivo.setText("❌ Error")
        self.ui.bt_cargar.setEnabled(True)
        self.ui.bt_iniciar.setEnabled(True)
        QMessageBox.critical(self, "Error del robot", f"Ocurrió un error:\n{msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())