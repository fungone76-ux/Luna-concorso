import os
import threading
import time
from pathlib import Path
from typing import Optional
import tkinter as tk
from tkinter import messagebox, filedialog
import sys
import textwrap

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from PIL import Image, ImageTk

from src.ai.gemini_client import GeminiClient, GeminiConfig
from src.domain.models import SessionState, Question
from src.engine.session_engine import SessionEngine
from src.engine.exam_engine import ExamEngine, ExamSession
from src.visuals.sd_client import SDClient, SDConfig
from src.voice_narrator import init_narrator, speak, stop, shutdown_narrator

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")


class ImagePopup(ctk.CTkToplevel):
    def __init__(self, image_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Visualizzatore Immagine")
        self.geometry("900x900")
        self.lift()
        self.focus_force()
        try:
            self.original_image = Image.open(image_path)
            self.im_width, self.im_height = self.original_image.size
            self.current_scale = 1.0
            self.canvas = ctk.CTkCanvas(self, bg="#101010", highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)
            self.tk_image = ImageTk.PhotoImage(self.original_image)
            self.image_id = self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
            self.canvas.bind("<ButtonPress-1>", self.move_from)
            self.canvas.bind("<B1-Motion>", self.move_to)
            self.canvas.bind("<MouseWheel>", self.zoom)
            self.update_scrollregion()
        except Exception as e:
            print(f"Errore popup: {e}")

    def move_from(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def move_to(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def zoom(self, event):
        if event.num == 5 or event.delta < 0:
            scale_factor = 0.9
        else:
            scale_factor = 1.1
        new_scale = self.current_scale * scale_factor
        if 0.1 < new_scale < 5.0:
            self.current_scale = new_scale
            new_w = int(self.im_width * self.current_scale)
            new_h = int(self.im_height * self.current_scale)
            resized = self.original_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.tk_image = ImageTk.PhotoImage(resized)
            self.canvas.itemconfig(self.image_id, image=self.tk_image)
            self.update_scrollregion()

    def update_scrollregion(self):
        self.canvas.config(scrollregion=self.canvas.bbox("all"))


class LunaGuiApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        init_narrator()
        self.project_root = str(Path(__file__).resolve().parent.parent)
        self._init_engine()
        self.session_state = SessionState()
        self.current_question: Optional[Question] = None
        self.last_image_path: Optional[str] = None
        self.can_answer = False

        # Variabili Esame
        self.exam_session: Optional[ExamSession] = None
        self.is_exam_mode = False
        self.exam_timer_id = None

        self.title("Luna Study - RIPAM Edition")
        self.geometry("600x1000")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=1)  # Main Content (Image/Exam)
        self.grid_rowconfigure(2, weight=0)  # Chat/Exam Text
        self.grid_rowconfigure(3, weight=0)  # Options
        self.grid_rowconfigure(4, weight=0)  # Input/Nav

        self._setup_ui()
        self.after(100, self.start_turn)  # Avvia modalità gioco di default

    def _init_engine(self):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        gemini = GeminiClient(GeminiConfig(api_key=api_key if api_key else "dummy"))
        sd = SDClient(SDConfig.from_env())
        self.engine = SessionEngine(self.project_root, gemini, sd, True)
        self.exam_engine = ExamEngine(self.project_root, gemini)

    def _setup_ui(self):
        # 1. HEADER
        self.header_frame = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#202c33")
        self.header_frame.grid(row=0, column=0, sticky="ew")

        self.lbl_tutor_info = ctk.CTkLabel(self.header_frame, text="Luna Bot", font=("Helvetica", 16, "bold"),
                                           text_color="white")
        self.lbl_tutor_info.pack(side="left", padx=15, pady=10)

        # Bottoni
        self.btn_exam = ctk.CTkButton(self.header_frame, text="SIMULAZIONE ESAME", width=120, height=30,
                                      fg_color="#b91c1c", hover_color="#991b1b", command=self.start_exam_mode)
        self.btn_exam.pack(side="right", padx=10, pady=10)

        self.btn_save = ctk.CTkButton(self.header_frame, text="💾", width=30, height=30, fg_color="#37404a",
                                      command=self.save_game)
        self.btn_save.pack(side="right", padx=5, pady=10)

        self.btn_load = ctk.CTkButton(self.header_frame, text="📂", width=30, height=30, fg_color="#37404a",
                                      command=self.load_game)
        self.btn_load.pack(side="right", padx=5, pady=10)

        self.lbl_stats = ctk.CTkLabel(self.header_frame, text="-- Statistiche --", font=("Helvetica", 12),
                                      text_color="#aebac1")
        self.lbl_stats.pack(side="right", padx=10, pady=10)

        # 2. IMAGE / EXAM STATUS AREA
        self.image_frame = ctk.CTkFrame(self, fg_color="#0b141a", corner_radius=0)
        self.image_frame.grid(row=1, column=0, sticky="nsew")

        self.image_label = ctk.CTkLabel(self.image_frame, text="", cursor="hand2")
        self.image_label.place(relx=0.5, rely=0.5, anchor="center")
        self.image_label.bind("<Button-1>", self.open_image_viewer)

        # Widget specifici Esame/Loading
        self.lbl_timer = ctk.CTkLabel(self.image_frame, text="", font=("Courier", 24, "bold"), text_color="#ef4444")

        self.loading_label = ctk.CTkLabel(self.image_frame, text="", text_color="#00a884",
                                          font=("Helvetica", 14, "bold"))
        self.loading_label.place(relx=0.5, rely=0.45, anchor="center")
        self.progress_bar = ctk.CTkProgressBar(self.image_frame, width=200, mode="indeterminate",
                                               progress_color="#00a884")

        # 3. CHAT BUBBLE
        self.chat_frame = ctk.CTkFrame(self, fg_color="#0b141a", corner_radius=0)
        self.chat_frame.grid(row=2, column=0, sticky="ew")
        self.bubble_frame = ctk.CTkFrame(self.chat_frame, fg_color="#202c33", corner_radius=15)
        self.bubble_frame.pack(fill="x", padx=15, pady=(10, 5))
        self.question_text = ctk.CTkLabel(self.bubble_frame, text="Caricamento...", font=("Helvetica", 15),
                                          wraplength=540, justify="left", anchor="w", text_color="#e9edef")
        self.question_text.pack(padx=15, pady=15, fill="x")

        # 4. OPTIONS
        self.options_frame = ctk.CTkFrame(self, fg_color="#0b141a", corner_radius=0)
        self.options_frame.grid(row=3, column=0, sticky="ew")
        self.btn_options = {}
        for letter in ["A", "B", "C", "D"]:
            btn = ctk.CTkButton(self.options_frame, text=letter, font=("Helvetica", 14), fg_color="#2a3942",
                                hover_color="#3a4a55", height=55, corner_radius=10, anchor="w",
                                command=lambda l=letter: self.submit_answer(l))
            self.btn_options[letter] = btn

        self.btn_next = ctk.CTkButton(self.options_frame, text="Prossima Domanda ➤", font=("Helvetica", 16, "bold"),
                                      fg_color="#00a884", height=50, corner_radius=10, command=self.start_turn)

        self.btn_skip = ctk.CTkButton(self.options_frame, text="SALTA (Omessa) ⏭️", font=("Helvetica", 14),
                                      fg_color="#eab308", hover_color="#ca8a04", height=40, corner_radius=10,
                                      command=lambda: self.submit_answer(None))

        # 5. INPUT (Solo gioco)
        self.input_frame = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#202c33")
        self.input_frame.grid(row=4, column=0, sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)
        self.entry_msg = ctk.CTkEntry(self.input_frame, placeholder_text="Scrivi...", fg_color="#2a3942",
                                      border_width=0, text_color="white", height=40, corner_radius=20)
        self.entry_msg.grid(row=0, column=0, padx=(15, 10), pady=10, sticky="ew")
        self.entry_msg.bind("<Return>", lambda event: self.send_message())
        self.btn_send = ctk.CTkButton(self.input_frame, text="➤", width=40, height=40, corner_radius=20,
                                      fg_color="#00a884", command=self.send_message)
        self.btn_send.grid(row=0, column=1, padx=(0, 15), pady=10)

    # --- NUOVA FUNZIONE STATISTICHE ---
    def _update_stats_display(self):
        """Calcola e aggiorna le statistiche in tempo reale per il tutor corrente."""
        if not self.current_question or self.is_exam_mode:
            return

        tutor = self.current_question.tutor

        # 1. Calcolo Statistiche dalla cronologia (History)
        total_questions = 0
        correct_answers = 0

        for h in self.session_state.history:
            if h.tutor == tutor:
                total_questions += 1
                if h.outcome == "corretta":
                    correct_answers += 1

        percentage = int((correct_answers / total_questions) * 100) if total_questions > 0 else 0

        # 2. Recupera Stage e Punti
        stage = self.session_state.stage.get(tutor, 1)
        points = self.session_state.progress.get(tutor, 0)

        # 3. Aggiorna Label
        stats_text = f"{tutor}: {correct_answers}/{total_questions} ({percentage}%) | Stage: {stage} | Punti: {points}"
        self.lbl_stats.configure(text=stats_text)

    # --- MODALITA' ESAME ---
    def start_exam_mode(self):
        stop()
        self.is_exam_mode = True
        self.exam_session = self.exam_engine.start_exam()

        self.image_label.configure(image="")
        self.image_label.image = None
        self.lbl_stats.configure(text="MODALITÀ ESAME")
        self.btn_exam.configure(state="disabled", text="ESAME IN CORSO")

        self.input_frame.grid_forget()
        self.lbl_timer.place(relx=0.5, rely=0.1, anchor="center")
        self._update_timer()
        self.btn_skip.pack(fill="x", padx=20, pady=(0, 10))

        self.next_exam_question()

    def next_exam_question(self):
        self.loading_label.configure(text="Caricamento quesito ministeriale...")
        self.progress_bar.place(relx=0.5, rely=0.5, anchor="center")
        self.progress_bar.start()
        self.set_ui_state("disabled")
        threading.Thread(target=self._exam_fetch_thread, daemon=True).start()

    def _exam_fetch_thread(self):
        q = self.exam_engine.get_next_question(self.exam_session)
        self.after(0, lambda: self._display_exam_question(q))

    def _display_exam_question(self, q: Question):
        self.progress_bar.stop()
        self.progress_bar.place_forget()
        self.loading_label.configure(text="")

        if not q:
            self._end_exam()
            return

        self.current_question = q
        self.can_answer = True

        idx = self.exam_session.current_index + 1
        total = len(self.exam_session.subject_roadmap)
        self.lbl_tutor_info.configure(text=f"Domanda {idx}/{total}")

        self.question_text.configure(text=f"[{q.materia}]\n\n{q.domanda}")

        for letter in ["A", "B", "C", "D"]:
            raw = q.opzioni.get(letter, "---")
            wrap = "\n".join(textwrap.wrap(raw, width=55))
            btn = self.btn_options[letter]
            btn.configure(text=f"{letter}) {wrap}", fg_color="#2a3942", state="normal")
            btn.pack(fill="x", padx=20, pady=4)

        self.btn_skip.configure(state="normal")

    def _update_timer(self):
        if not self.is_exam_mode or not self.exam_session: return
        elapsed = time.time() - self.exam_session.start_time
        remaining = self.exam_session.duration_seconds - elapsed
        if remaining <= 0:
            self._end_exam()
            return
        mins, secs = divmod(int(remaining), 60)
        self.lbl_timer.configure(text=f"{mins:02d}:{secs:02d}")
        self.exam_timer_id = self.after(1000, self._update_timer)

    def _end_exam(self):
        if self.exam_timer_id: self.after_cancel(self.exam_timer_id)
        self.is_exam_mode = False
        score, passed, report = self.exam_engine.calculate_result(self.exam_session)
        self.question_text.configure(text=report)
        for btn in self.btn_options.values(): btn.pack_forget()
        self.btn_skip.pack_forget()
        self.lbl_timer.place_forget()
        self.btn_exam.configure(state="normal", text="SIMULAZIONE ESAME")
        self.btn_next.pack(fill="x", padx=20, pady=10)
        self.btn_next.configure(text="Torna al Gioco", command=self.restore_game_mode)

    def restore_game_mode(self):
        self.is_exam_mode = False
        self.input_frame.grid(row=4, column=0, sticky="ew")
        self.btn_next.configure(text="Prossima Domanda ➤", command=self.start_turn)
        self.start_turn()

    # --- LOGICA GIOCO ---
    def start_turn(self):
        stop()
        self.is_exam_mode = False
        self.set_ui_state("disabled")
        self.btn_next.pack_forget()
        self.btn_skip.pack_forget()
        self.lbl_timer.place_forget()

        self.loading_label.configure(text="Generazione domanda con Gemini...")
        self.progress_bar.place(relx=0.5, rely=0.5, anchor="center")
        self.progress_bar.start()

        threading.Thread(target=self._generate_question_thread, daemon=True).start()

    def _generate_question_thread(self):
        try:
            q = self.engine.start_next_question(self.session_state)
            self.after(0, lambda: self._display_question(q))
        except Exception as e:
            print(f"Errore generazione: {e}")

    def _display_question(self, q: Question):
        self.progress_bar.stop()
        self.progress_bar.place_forget()
        self.loading_label.configure(text="")

        self.current_question = q
        self.can_answer = True
        self.question_text.configure(text=q.domanda)

        for letter in ["A", "B", "C", "D"]:
            raw = q.opzioni.get(letter, "---")
            wrap = "\n".join(textwrap.wrap(raw, width=55))
            btn = self.btn_options[letter]
            btn.configure(text=f"{letter}) {wrap}", fg_color="#2a3942", state="normal")
            btn.pack(fill="x", padx=20, pady=4)

        tutor = q.tutor
        self.lbl_tutor_info.configure(text=f"{tutor} (Online)")

        # AGGIORNAMENTO STATISTICHE VISIVE
        self._update_stats_display()

        self.entry_msg.configure(state="normal")
        self.btn_send.configure(state="normal")
        self.entry_msg.delete(0, "end")
        self.entry_msg.focus()

        text_to_read = f"Domanda. {q.domanda}. "
        for l in ["A", "B", "C", "D"]:
            if q.opzioni.get(l): text_to_read += f"Risposta {l}. {q.opzioni[l]}. "
        speak(text_to_read)

    def submit_answer(self, choice: str):
        if not self.can_answer: return
        stop()
        self.can_answer = False

        if self.is_exam_mode:
            self.exam_engine.submit_answer(self.exam_session, choice)
            self.exam_session.current_index += 1
            self.next_exam_question()
        else:
            self.loading_label.configure(text="Analisi risposta...")
            self.progress_bar.place(relx=0.5, rely=0.5, anchor="center")
            self.progress_bar.start()
            threading.Thread(target=self._process_game_answer_thread, args=(choice,), daemon=True).start()

    def _process_game_answer_thread(self, choice):
        res = self.engine.apply_answer(self.session_state, self.current_question, choice)
        image_path = self.engine.last_image_path
        self.after(0, lambda: self._show_result(res, image_path, choice))

    def _show_result(self, res, image_path, user_choice):
        self.progress_bar.stop()
        self.progress_bar.place_forget()
        self.loading_label.configure(text="")

        # AGGIORNAMENTO STATISTICHE POST-RISPOSTA
        self._update_stats_display()

        self.last_image_path = image_path
        for btn in self.btn_options.values(): btn.pack_forget()

        icon = "✅" if res.outcome == "corretta" else "❌"
        spieg = getattr(self.current_question, "spiegazione_breve", "")
        fb = f"{icon} Risposta {res.outcome.upper()}!\nCorretta: {self.current_question.corretta}\n\n{spieg}"
        self.question_text.configure(text=fb)

        self.btn_next.pack(fill="x", padx=20, pady=10)

        if image_path and os.path.exists(image_path):
            self._load_image_to_ui(image_path)
        else:
            self.loading_label.configure(text="Nessuna immagine generata")

        self.entry_msg.configure(state="normal")
        self.btn_send.configure(state="normal")
        self.entry_msg.focus()

        audio_fb = f"Risposta {res.outcome}. "
        if res.outcome != "corretta": audio_fb += f"La giusta era {self.current_question.corretta}. "
        audio_fb += spieg
        speak(audio_fb)

    def save_game(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if file_path: self.engine.save_session_to_file(self.session_state, file_path)

    def load_game(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if file_path:
            ns = self.engine.load_session_from_file(file_path)
            if ns:
                self.session_state = ns
                self.start_turn()

    def send_message(self):
        if not self.current_question: return
        text = self.entry_msg.get().strip()
        if not text: return
        self.entry_msg.delete(0, "end")
        upper = text.upper()
        if self.can_answer and upper in ["A", "B", "C", "D"]:
            self.submit_answer(upper)
        else:
            cur = self.question_text.cget("text")
            self.question_text.configure(text=f"{cur}\n\nTu: {text}")
            threading.Thread(target=self._chat_thread, args=(text,), daemon=True).start()

    def _chat_thread(self, text):
        has_answered = not self.can_answer
        resp = self.engine.get_tutor_response(self.current_question, text, has_answered)
        self.after(0, lambda: self._update_chat(resp))

    def _update_chat(self, text):
        cur = self.question_text.cget("text")
        self.question_text.configure(text=f"{cur}\n\n{self.current_question.tutor}: {text}")
        speak(text)

    def _load_image_to_ui(self, path):
        try:
            pil = Image.open(path)
            w = self.image_frame.winfo_width() or 500
            h = self.image_frame.winfo_height() or 500
            r = min(w / pil.width, h / pil.height)
            tk_img = ImageTk.PhotoImage(pil.resize((int(pil.width * r), int(pil.height * r)), Image.Resampling.LANCZOS))
            self.image_label.configure(image=tk_img)
            self.image_label.image = tk_img
        except:
            pass

    def open_image_viewer(self, e=None):
        if self.last_image_path: ImagePopup(self.last_image_path, self)

    def set_ui_state(self, state):
        for btn in self.btn_options.values(): btn.configure(state=state)
        self.btn_skip.configure(state=state)
        self.entry_msg.configure(state=state)
        self.btn_send.configure(state=state)

    def on_close(self):
        shutdown_narrator()
        self.destroy()


if __name__ == "__main__":
    app = LunaGuiApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()