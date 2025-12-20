import os
import threading
from pathlib import Path
from typing import Optional
import tkinter as tk
from tkinter import messagebox
import sys
import textwrap  # Per mandare a capo il testo lungo

# Aggiunge il path per i moduli
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from PIL import Image, ImageTk

from src.ai.gemini_client import GeminiClient, GeminiConfig
from src.domain.models import SessionState, Question
from src.engine.session_engine import SessionEngine
from src.visuals.sd_client import SDClient, SDConfig

# Configurazione aspetto "WhatsApp Dark"
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")


class ImagePopup(ctk.CTkToplevel):
    """
    Finestra popup avanzata per visualizzare l'immagine con ZOOM e PAN.
    """

    def __init__(self, image_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Visualizzatore Immagine")
        self.geometry("900x900")

        try:
            self.original_image = Image.open(image_path)
            self.im_width, self.im_height = self.original_image.size
            self.im_scale = 1.0
            self.delta = 1.3

            self.canvas = ctk.CTkCanvas(self, bg="#101010", highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)

            self.tk_image = ImageTk.PhotoImage(self.original_image)
            self.image_id = self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

            # Binding Mouse
            self.canvas.bind("<ButtonPress-1>", self.move_from)
            self.canvas.bind("<B1-Motion>", self.move_to)
            self.canvas.bind("<MouseWheel>", self.wheel)  # Windows
            self.canvas.bind("<Button-4>", self.wheel)  # Linux scroll up
            self.canvas.bind("<Button-5>", self.wheel)  # Linux scroll down

            self.show_image()

        except Exception as e:
            print(f"Errore popup: {e}")

    def move_from(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def move_to(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.show_image()

    def wheel(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        if event.num == 5 or event.delta < 0:
            scale = 1.0 / self.delta
        else:
            scale = self.delta
        new_scale = self.im_scale * scale
        if 0.1 < new_scale < 20.0:
            self.im_scale = new_scale
            self.canvas.scale("all", x, y, scale, scale)
            self.show_image()

    def show_image(self):
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)


class LunaGuiApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CONFIGURAZIONE ENGINE ---
        self.project_root = str(Path(__file__).resolve().parent.parent)
        self._init_engine()
        self.session_state = SessionState()
        self.current_question: Optional[Question] = None
        self.last_image_path: Optional[str] = None

        # --- CONFIGURAZIONE FINESTRA ---
        self.title("Luna Study - Chat Mode")
        self.geometry("600x1000")  # Un po' più alto per far stare tutto

        # Layout principale
        self.grid_columnconfigure(0, weight=1)

        # Righe:
        # 0: Header
        # 1: Immagine (pesante, si espande)
        # 2: Bolla domanda (si adatta)
        # 3: Opzioni (pulsanti verticali)
        # 4: Input Bar (fissa in basso)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)

        self._setup_ui()
        self.after(100, self.start_turn)

    def _init_engine(self):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        gemini = GeminiClient(GeminiConfig(api_key=api_key if api_key else "dummy"))
        sd = SDClient(SDConfig.from_env())
        self.engine = SessionEngine(
            project_root=self.project_root,
            gemini=gemini,
            sd_client=sd,
            enable_sd=True
        )

    def _setup_ui(self):
        # 1. HEADER
        self.header_frame = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#202c33")
        self.header_frame.grid(row=0, column=0, sticky="ew")

        self.lbl_tutor_info = ctk.CTkLabel(self.header_frame, text="Luna Study Bot", font=("Helvetica", 16, "bold"),
                                           text_color="white")
        self.lbl_tutor_info.pack(side="left", padx=20, pady=10)

        self.lbl_stats = ctk.CTkLabel(self.header_frame, text="Stage: 1 | Punti: 0", font=("Helvetica", 12),
                                      text_color="#aebac1")
        self.lbl_stats.pack(side="right", padx=20, pady=10)

        # 2. IMAGE AREA
        self.image_frame = ctk.CTkFrame(self, fg_color="#0b141a", corner_radius=0)
        self.image_frame.grid(row=1, column=0, sticky="nsew")

        self.image_label = ctk.CTkLabel(self.image_frame, text="", cursor="hand2")
        self.image_label.place(relx=0.5, rely=0.5, anchor="center")
        self.image_label.bind("<Button-1>", self.open_image_viewer)

        self.loading_label = ctk.CTkLabel(self.image_frame, text="", text_color="gray")
        self.loading_label.place(relx=0.5, rely=0.5, anchor="center")

        # 3. CHAT BUBBLE (DOMANDA)
        self.chat_frame = ctk.CTkFrame(self, fg_color="#0b141a", corner_radius=0)
        self.chat_frame.grid(row=2, column=0, sticky="ew", padx=0, pady=0)

        self.bubble_frame = ctk.CTkFrame(self.chat_frame, fg_color="#202c33", corner_radius=15)
        self.bubble_frame.pack(fill="x", padx=15, pady=(10, 5))

        self.question_text = ctk.CTkLabel(self.bubble_frame, text="Caricamento...", font=("Helvetica", 15),
                                          wraplength=540, justify="left", anchor="w", text_color="#e9edef")
        self.question_text.pack(padx=15, pady=15, fill="x")

        # 4. OPTIONS (PULSANTI VERTICALI)
        # Usiamo uno ScrollableFrame se le opzioni sono lunghissime, o un frame normale.
        # Per ora Frame normale dato che lo schermo è alto.
        self.options_frame = ctk.CTkFrame(self, fg_color="#0b141a", corner_radius=0)
        self.options_frame.grid(row=3, column=0, sticky="ew", padx=0, pady=0)

        self.btn_options = {}
        letters = ["A", "B", "C", "D"]
        for letter in letters:
            # Button alto per contenere testo su più righe
            btn = ctk.CTkButton(
                self.options_frame,
                text=f"{letter}",
                font=("Helvetica", 14),
                fg_color="#2a3942",
                hover_color="#3a4a55",
                height=55,  # Più alto
                corner_radius=10,
                anchor="w",  # Testo allineato a sinistra
                command=lambda l=letter: self.submit_answer(l)
            )
            # Pack verticale per avere tutta la larghezza
            btn.pack(fill="x", padx=20, pady=4)
            self.btn_options[letter] = btn

        # 5. INPUT BAR (CHAT STYLE)
        self.input_frame = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#202c33")
        self.input_frame.grid(row=4, column=0, sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)  # Entry prende tutto lo spazio
        self.input_frame.grid_columnconfigure(1, weight=0)  # Bottone fisso

        self.entry_msg = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Scrivi un messaggio... (o A/B/C/D)",
            fg_color="#2a3942",
            border_width=0,
            text_color="white",
            height=40,
            corner_radius=20
        )
        self.entry_msg.grid(row=0, column=0, padx=(15, 10), pady=10, sticky="ew")
        # Bind tasto Invio
        self.entry_msg.bind("<Return>", lambda event: self.send_message())

        self.btn_send = ctk.CTkButton(
            self.input_frame,
            text="➤",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="#00a884",
            hover_color="#008f6f",
            command=self.send_message
        )
        self.btn_send.grid(row=0, column=1, padx=(0, 15), pady=10)

    # --- LOGICA ---

    def start_turn(self):
        self.set_ui_state("disabled")
        self.loading_label.configure(text="Generazione domanda...")
        threading.Thread(target=self._generate_question_thread, daemon=True).start()

    def _generate_question_thread(self):
        try:
            q = self.engine.start_next_question(self.session_state)
            self.after(0, lambda: self._display_question(q))
        except Exception as e:
            print(f"Errore: {e}")

    def _display_question(self, q: Question):
        self.current_question = q

        # Testo Domanda
        self.question_text.configure(text=q.domanda)

        # Testo Opzioni con WRAPPING
        for letter in ["A", "B", "C", "D"]:
            raw_text = q.opzioni.get(letter, "---")
            # Funzione wrap: spezza le righe ogni 55 caratteri circa
            wrapped_text = "\n".join(textwrap.wrap(raw_text, width=55))

            display_text = f"{letter}) {wrapped_text}"
            self.btn_options[letter].configure(text=display_text, fg_color="#2a3942")

        # Stats
        tutor = q.tutor
        prog = self.session_state.progress.get(tutor, 0)
        stage = self.session_state.stage.get(tutor, 1)
        self.lbl_tutor_info.configure(text=f"{tutor} (Online)")
        self.lbl_stats.configure(text=f"Stage: {stage} | Punti: {prog}")

        self.loading_label.configure(text="")
        self.set_ui_state("normal")
        self.entry_msg.delete(0, "end")  # Pulisci input
        self.entry_msg.focus()

    def send_message(self):
        """Gestisce l'invio dalla barra di testo."""
        if not self.current_question:
            return

        text = self.entry_msg.get().strip().upper()
        if not text:
            return

        # Se l'utente scrive A, B, C, D, lo trattiamo come risposta
        if text in ["A", "B", "C", "D"]:
            self.submit_answer(text)
        else:
            # Qui potresti implementare logica di chat, per ora ignoriamo o diamo errore
            # messagebox.showinfo("Chat", f"Hai scritto: {text}\n(Usa i pulsanti o scrivi A/B/C/D per rispondere)")
            pass

        self.entry_msg.delete(0, "end")

    def submit_answer(self, choice: str):
        if not self.current_question: return
        self.set_ui_state("disabled")

        # Feedback visivo immediato sulla scelta
        self.btn_options[choice].configure(fg_color="#005c4b")  # Verde scuro (Selected)

        self.loading_label.configure(text="Generazione immagine...")
        threading.Thread(target=self._process_answer_thread, args=(choice,), daemon=True).start()

    def _process_answer_thread(self, choice: str):
        res = self.engine.apply_answer(self.session_state, self.current_question, choice)
        image_path = self.engine.last_image_path
        self.after(0, lambda: self._show_result(res, image_path, choice))

    def _show_result(self, res, image_path, user_choice):
        self.last_image_path = image_path
        correct = self.current_question.corretta

        # Mostra corretta/errata
        if correct: self.btn_options[correct].configure(fg_color="#00a884")
        if user_choice != correct and user_choice is not None:
            self.btn_options[user_choice].configure(fg_color="#ef5350")

        self.lbl_stats.configure(text=f"Stage: {res.new_stage} | Punti: {res.new_progress}")

        if image_path and os.path.exists(image_path):
            self._load_image_to_ui(image_path)
            self.loading_label.configure(text="")
        else:
            self.loading_label.configure(text="Nessuna immagine generata")

        # Pausa e next
        self.after(3500, self.start_turn)

    def _load_image_to_ui(self, path):
        try:
            pil_img = Image.open(path)
            # Adatta al frame
            w = self.image_frame.winfo_width()
            h = self.image_frame.winfo_height()
            if w < 100: w = 500
            if h < 100: h = 500

            ratio = min(w / pil_img.width, h / pil_img.height)
            new_w = int(pil_img.width * ratio)
            new_h = int(pil_img.height * ratio)
            resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(resized)
            self.image_label.configure(image=tk_img)
            self.image_label.image = tk_img
        except Exception as e:
            print(f"Errore img: {e}")

    def open_image_viewer(self, event=None):
        if self.last_image_path and os.path.exists(self.last_image_path):
            ImagePopup(self.last_image_path, self)

    def set_ui_state(self, state):
        for btn in self.btn_options.values():
            btn.configure(state=state)
        self.entry_msg.configure(state=state)
        self.btn_send.configure(state=state)


if __name__ == "__main__":
    app = LunaGuiApp()
    app.mainloop()