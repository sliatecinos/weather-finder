import os
import sys
import tkinter as tk
import unittest

# Adiciona a raiz do projeto ao path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from weather_finder import WeatherFinderApp


class TestResponsiveAlerts(unittest.TestCase):
    """Testes automatizados para validação da responsividade dos alertas climáticos."""

    def setUp(self):
        self.root = tk.Tk()
        self.app = WeatherFinderApp(self.root)
        if self.app._timer:
            self.app._timer.cancel()

        self.mock_weather = {
            "atual": {
                "temperatura": 24.5,
                "condicao": "Parcialmente nublado",
                "umidade": 65,
                "vento": 12.0,
            }
        }

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_single_alert_responsiveness(self):
        """Valida a quebra de texto (wraplength) em redimensionamentos, maximização e restauração."""
        alerts = [
            {
                "severidade": "Perigo Potencial",
                "descricao": "Chuva Intensa com acumulados expressivos em curto intervalo.",
                "riscos": ["Alagamentos", "Rajadas de vento"],
            }
        ]

        # 1. Renderização inicial (720x620)
        self.app._update_gui("São Paulo", self.mock_weather, alerts, "Log inicial\n")
        self.root.update()

        labels = [w for w in self.app.alert_frame.winfo_children() if isinstance(w, tk.Label)]
        self.assertEqual(len(labels), 1)
        lbl = labels[0]

        frame_w = self.app.alert_frame.winfo_width()
        self.assertEqual(lbl.cget("wraplength"), frame_w - 28)

        # 2. Redimensionamento manual para 1200x600
        self.root.geometry("1200x600")
        self.root.update()
        frame_w = self.app.alert_frame.winfo_width()
        self.assertEqual(frame_w, 1200)
        self.assertEqual(lbl.cget("wraplength"), 1200 - 28)

        # 3. Maximização (state zoomed)
        self.root.state("zoomed")
        self.root.update()
        zoomed_w = self.app.alert_frame.winfo_width()
        self.assertGreater(zoomed_w, 1200)
        self.assertEqual(lbl.cget("wraplength"), zoomed_w - 28)

        # 4. Restauração (state normal)
        self.root.state("normal")
        self.root.geometry("720x620")
        self.root.update()
        self.assertEqual(self.app.alert_frame.winfo_width(), 720)
        self.assertEqual(lbl.cget("wraplength"), 720 - 28)

        # 5. Tamanho mínimo (620x420)
        self.root.geometry("620x420")
        self.root.update()
        self.assertEqual(self.app.alert_frame.winfo_width(), 620)
        self.assertEqual(lbl.cget("wraplength"), 620 - 28)

    def test_multiple_alerts_responsiveness(self):
        """Valida se múltiplos alertas simultâneos atualizam o wraplength em conjunto."""
        multi_alerts = [
            {
                "severidade": "Grande Perigo",
                "descricao": "Acumulado de Chuva Extremo com deslizamentos na serra.",
                "riscos": ["Deslizamentos", "Inundações"],
            },
            {
                "severidade": "Perigo",
                "descricao": "Vendaval com rajadas de até 90 km/h.",
                "riscos": ["Queda de árvores", "Destelhamento"],
            },
            {
                "severidade": "Perigo Potencial",
                "descricao": "Declínio acentuado de temperatura.",
                "riscos": ["Geada"],
            },
        ]

        self.app._update_gui("Curitiba", self.mock_weather, multi_alerts, "Log multi alertas\n")
        self.root.update()

        labels = [w for w in self.app.alert_frame.winfo_children() if isinstance(w, tk.Label)]
        self.assertEqual(len(labels), 3)

        # Na largura inicial
        for idx, lbl in enumerate(labels):
            self.assertEqual(lbl.cget("wraplength"), 720 - 28, f"Label {idx} inicial incorreto")

        # Na maximização
        self.root.state("zoomed")
        self.root.update()
        zoomed_w = self.app.alert_frame.winfo_width()
        for idx, lbl in enumerate(labels):
            self.assertEqual(lbl.cget("wraplength"), zoomed_w - 28, f"Label {idx} no zoom incorreto")

        # Na restauração
        self.root.state("normal")
        self.root.geometry("720x620")
        self.root.update()
        for idx, lbl in enumerate(labels):
            self.assertEqual(lbl.cget("wraplength"), 720 - 28, f"Label {idx} restaurado incorreto")

    def test_alert_clear_and_reappear(self):
        """Valida ocultação do alert_frame quando não há alertas e reinicialização correta."""
        alerts = [
            {
                "severidade": "Perigo",
                "descricao": "Tempestade severa.",
                "riscos": ["Granizo"],
            }
        ]

        # Exibir alerta
        self.app._update_gui("Porto Alegre", self.mock_weather, alerts, "Alerta ativo\n")
        self.root.update()
        self.assertTrue(self.app.alert_frame.winfo_ismapped())

        # Limpar alerta
        self.app._update_gui("Porto Alegre", self.mock_weather, [], "Sem alertas\n")
        self.root.update()
        self.assertFalse(self.app.alert_frame.winfo_ismapped())
        self.assertEqual(self.app._last_alert_width, 0)

        # Reexibir alerta
        self.app._update_gui("Porto Alegre", self.mock_weather, alerts, "Alerta voltou\n")
        self.root.update()
        self.assertTrue(self.app.alert_frame.winfo_ismapped())
        labels = [w for w in self.app.alert_frame.winfo_children() if isinstance(w, tk.Label)]
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0].cget("wraplength"), self.app.alert_frame.winfo_width() - 28)


if __name__ == "__main__":
    unittest.main()
