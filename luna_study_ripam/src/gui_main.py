import os
import threading
from pathlib import Path
from typing import Optional
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

# Importa le classi del tuo motore esistente
# Assicurati di avere le righe per il path se lo lanci come script senza -m
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai.gemini_client import GeminiClient, GeminiConfig
from src.domain.models import SessionState, Question
from src.engine.session_engine import SessionEngine
from src.visuals.sd_client import SDClient, SDConfig

# Configurazione aspetto
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ImagePopup(ctk.CTkToplevel):
    """Finestra popup per visualizzare l'immagine ingrandita."""

    def __init__(self, image_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Visualizzatore Immagine")
        self.geometry("900x900")

        self.original_image = Image.open(image_path)
        self.tk_image = ImageTk.PhotoImage(self.original_image)

        self.canvas = ctk.CTkCanvas(self, bg="#202020", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.image_id = self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

        self.v_scroll = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.h_scroll = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")

        self.canvas.config(scrollregion=self.canvas.bbox("all"))


class LunaGuiApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CONFIGURAZIONE ENGINE ---
        self.project_root = str(Path(__file__).resolve().parent.parent)
        self._init_engine()

        # CORREZIONE QUI: Rinominato da self.state a self.session_state
        self.session_state = SessionState()

        self.current_question: Optional[Question] = None
        self.last_image_path: Optional[str] = None

        # --- CONFIGURAZIONE FINESTRA ---
        self.title("Luna Study - RIPAM Edition")
        self.geometry("1280x720")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self._setup_left_panel()
        self._setup_right_panel()

        self.after(100, self.start_turn)

    def _init_engine(self):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            # Fallback se non è nell'env, prova a cercarla in un file .env se usi python-dotenv
            # Per ora mostriamo errore
            print("WARN: GEMINI_API_KEY non trovata nelle variabili d'ambiente.")

        # Se vuoi evitare il crash se manca la chiave, gestiscilo qui,
        # ma per ora assumiamo che tu l'abbia settata nel terminale o .env
        gemini = GeminiClient(GeminiConfig(api_key=api_key if api_key else "dummy"))
        sd = SDClient(SDConfig.from_env())

        self.engine = SessionEngine(
            project_root=self.project_root,
            gemini=gemini,
            sd_client=sd,
            enable_sd=True
        )

    def _setup_left_panel(self):
        self.left_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.left_frame.grid_rowconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(1, weight=0)

        self.image_label = ctk.CTkLabel(self.left_frame, text="In attesa di generazione...", font=("Arial", 16))
        self.image_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.image_label.bind("<Button-1>", self.open_image_viewer)
        self.image_label.configure(cursor="hand2")

        self.stats_frame = ctk.CTkFrame(self.left_frame, fg_color="#2b2b2b", corner_radius=10)
        self.stats_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=20)

        self.lbl_tutor = ctk.CTkLabel(self.stats_frame, text="Tutor: --", font=("Roboto Medium", 16))
        self.lbl_tutor.pack(pady=(10, 5), padx=10, anchor="w")

        self.lbl_correct = ctk.CTkLabel(self.stats_frame, text="Risposte Esatte: 0", font=("Roboto", 14),
                                        text_color="#00ff88")
        self.lbl_correct.pack(pady=2, padx=10, anchor="w")

        self.lbl_stage = ctk.CTkLabel(self.stats_frame, text="Stage Raggiunto: 1", font=("Roboto", 14),
                                      text_color="#4facfe")
        self.lbl_stage.pack(pady=(2, 10), padx=10, anchor="w")

    def _setup_right_panel(self):
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#121212")
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=0)

        self.chat_area = ctk.CTkScrollableFrame(self.right_frame, fg_color="transparent")
        self.chat_area.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        self.question_text = ctk.CTkLabel(
            self.chat_area,
            text="Caricamento domanda...",
            font=("Roboto Medium", 20),
            wraplength=600,
            justify="left",
            anchor="w"
        )
        self.question_text.pack(fill="x", pady=(50, 20))

        self.options_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.options_frame.grid(row=1, column=0, sticky="ew", padx=30, pady=30)

        self.btn_options = {}
        letters = ["A", "B", "C", "D"]
        for i, letter in enumerate(letters):
            btn = ctk.CTkButton(
                self.options_frame,
                text=f"{letter}) ...",
                font=("Roboto", 15),
                fg_color="#2b2b2b",
                hover_color="#3a3a3a",
                height=50,
                command=lambda l=letter: self.submit_answer(l)
            )
            row = i // 2
            col = i % 2
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
            self.btn_options[letter] = btn

        self.options_frame.grid_columnconfigure(0, weight=1)
        self.options_frame.grid_columnconfigure(1, weight=1)

        self.status_bar = ctk.CTkLabel(self.right_frame, text="In attesa...", text_color="gray")
        self.status_bar.grid(row=2, column=0, sticky="ew", pady=(0, 5))

    def start_turn(self):
        self.set_ui_state("disabled")
        self.status_bar.configure(text="Generazione domanda con Gemini...")
        threading.Thread(target=self._generate_question_thread, daemon=True).start()

    def _generate_question_thread(self):
        try:
            # CORREZIONE QUI: usa self.session_state
            q = self.engine.start_next_question(self.session_state)
            self.after(0, lambda: self._display_question(q))
        except Exception as e:
            print(f"Errore generazione: {e}")
            self.after(0, lambda: messagebox.showerror("Errore", f"Errore generazione: {e}"))

    def _display_question(self, q: Question):
        self.current_question = q
        self.question_text.configure(text=q.domanda)

        for letter in ["A", "B", "C", "D"]:
            text = q.opzioni.get(letter, "---")
            self.btn_options[letter].configure(text=f"{letter}) {text}", fg_color="#2b2b2b")

        tutor = q.tutor
        # CORREZIONE QUI: usa self.session_state
        prog = self.session_state.progress.get(tutor, 0)
        stage = self.session_state.stage.get(tutor, 1)
        self._update_stats_labels(tutor, prog, stage)

        # CORREZIONE QUI: usa self.session_state
        self.status_bar.configure(
            text=f"Domanda {self.session_state.question_index} / {self.session_state.total_questions}")
        self.set_ui_state("normal")

    def submit_answer(self, choice: str):
        if not self.current_question:
            return

        self.set_ui_state("disabled")
        self.status_bar.configure(text="Verifica risposta e generazione immagine...")
        self.btn_options[choice].configure(fg_color="#d69e2e")

        threading.Thread(target=self._process_answer_thread, args=(choice,), daemon=True).start()

    def _process_answer_thread(self, choice: str):
        # CORREZIONE QUI: usa self.session_state
        res = self.engine.apply_answer(self.session_state, self.current_question, choice)

        # L'engine ha già salvato il path dell'immagine in self.engine.last_image_path
        image_path = self.engine.last_image_path
        self.after(0, lambda: self._show_result(res, image_path, choice))

    def _show_result(self, res, image_path, user_choice):
        self.last_image_path = image_path

        correct_letter = self.current_question.corretta
        if correct_letter:
            self.btn_options[correct_letter].configure(fg_color="#38a169")

        if user_choice != correct_letter and user_choice is not None:
            self.btn_options[user_choice].configure(fg_color="#e53e3e")

        self._update_stats_labels(res.tutor, res.new_progress, res.new_stage)

        if image_path and os.path.exists(image_path):
            self._load_image_to_ui(image_path)
        else:
            self.image_label.configure(text="Nessuna immagine generata", image=None)

        self.status_bar.configure(text=f"Risultato: {res.outcome.upper()}. Caricamento prossima...")
        self.after(3000, self.start_turn)

    def _update_stats_labels(self, tutor, progress, stage):
        self.lbl_tutor.configure(text=f"Tutor: {tutor}")
        self.lbl_correct.configure(text=f"Risposte Esatte ({tutor}): {progress}")
        self.lbl_stage.configure(text=f"Stage Raggiunto: {stage}")

    def _load_image_to_ui(self, path):
        try:
            pil_img = Image.open(path)
            w = self.left_frame.winfo_width()
            h = self.left_frame.winfo_height() - 150
            if w < 100: w = 400
            if h < 100: h = 600

            ratio = min(w / pil_img.width, h / pil_img.height)
            new_w = int(pil_img.width * ratio)
            new_h = int(pil_img.height * ratio)

            resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(resized)

            self.image_label.configure(image=tk_img, text="")
            self.image_label.image = tk_img
        except Exception as e:
            print(f"Errore caricamento immagine UI: {e}")

    def open_image_viewer(self, event=None):
        if self.last_image_path and os.path.exists(self.last_image_path):
            ImagePopup(self.last_image_path, self)

    def set_ui_state(self, state):
        for btn in self.btn_options.values():
            btn.configure(state=state)


if __name__ == "__main__":
    app = LunaGuiApp()
    app.mainloop()