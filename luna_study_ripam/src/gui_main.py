# src/gui_main.py
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
            self.canvas.bind("<Button-4>", self.zoom_linux)
            self.canvas.bind("<Button-5>", self.zoom_linux)
            self.update_scrollregion()
        except:
            pass

    def move_from(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def move_to(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def zoom(self, event):
        self._do_zoom(1.1 if event.delta > 0 else 0.9)

    def zoom_linux(self, event):
        self._do_zoom(1.1 if event.num == 4 else 0.9)

    def _do_zoom(self, f):
        s = self.current_scale * f
        if 0.1 < s < 5.0:
            self.current_scale = s
            w, h = int(self.im_width * s), int(self.im_height * s)
            self.tk_image = ImageTk.PhotoImage(self.original_image.resize((w, h), Image.Resampling.LANCZOS))
            self.canvas.itemconfig(self.image_id, image=self.tk_image)
            self.update_scrollregion()

    def update_scrollregion(self):
        self.canvas.config(scrollregion=self.canvas.bbox("all"))


class LunaGuiApp(ctk.CTk):
    # Inserisci questo codice dentro la classe LunaGuiApp in src/gui_main.py

    def __init__(self):
        super().__init__()
        init_narrator()
        self.project_root = str(Path(__file__).resolve().parent.parent)
        self._init_engine()
        self.session_state = SessionState()
        self.current_question: Optional[Question] = None
        self.last_image_path: Optional[str] = None
        self.can_answer = False
        self.step = "start"

        self.exam_session = None
        self.is_exam_mode = False
        self.exam_timer_id = None

        self.title("Luna Study - Masterclass Desktop")
        self.geometry("1200x850")

        self.grid_columnconfigure(0, weight=0, minsize=450)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        # 1. Costruisci l'interfaccia di gioco (che rimarrà "sotto" o nascosta)
        self._setup_ui()

        # 2. Invece di avviare subito, mostra la SCHERMATA INIZIALE
        # self.after(100, self.start_new_block)  <-- RIMOSSO
        self.show_start_screen()  # <-- AGGIUNTO

    def show_start_screen(self):
        """Crea un frame a tutto schermo per il menu principale."""
        self.start_frame = ctk.CTkFrame(self, fg_color="#111827", corner_radius=0)
        self.start_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Contenitore centrale per allineamento
        center_frame = ctk.CTkFrame(self.start_frame, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")

        # LOGO / TITOLO
        title_label = ctk.CTkLabel(
            center_frame,
            text="LUNA STUDY\nRIPAM EDITION",
            font=("Roboto Medium", 40, "bold"),
            text_color="#10b981",
            justify="center"
        )
        title_label.pack(pady=(0, 40))

        # PULSANTE NUOVA PARTITA
        btn_new = ctk.CTkButton(
            center_frame,
            text="✨ NUOVA PARTITA",
            font=("Roboto Medium", 20),
            fg_color="#059669",
            hover_color="#047857",
            width=280,
            height=60,
            corner_radius=30,
            command=self.on_new_game
        )
        btn_new.pack(pady=15)

        # PULSANTE CARICA PARTITA
        btn_load = ctk.CTkButton(
            center_frame,
            text="📂 CARICA PARTITA",
            font=("Roboto Medium", 20),
            fg_color="#374151",
            hover_color="#4b5563",
            width=280,
            height=60,
            corner_radius=30,
            command=self.on_load_game_start
        )
        btn_load.pack(pady=15)

        # FOOTER
        footer = ctk.CTkLabel(
            self.start_frame,
            text="Powered by Gemini & Stable Diffusion",
            font=("Arial", 12),
            text_color="#6b7280"
        )
        footer.place(relx=0.5, rely=0.95, anchor="center")

    def on_new_game(self):
        """Avvia una nuova sessione."""
        # Distrugge la schermata iniziale con un'animazione o semplicemente la rimuove
        self.start_frame.destroy()
        # Avvia la logica di gioco esistente
        self.start_new_block()

    def on_load_game_start(self):
        """Gestisce il caricamento dalla schermata iniziale."""
        file_path = filedialog.askopenfilename(filetypes=[("Salvataggio Luna", "*.json")])
        if file_path:
            ns = self.engine.load_session_from_file(file_path)
            if ns:
                self.session_state = ns
                self.start_frame.destroy()  # Rimuove il menu solo se il caricamento va a buon fine
                self.show_summary_screen()

    def _init_engine(self):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        gemini = GeminiClient(GeminiConfig(api_key=api_key if api_key else "dummy"))
        sd = SDClient(SDConfig.from_env())
        self.engine = SessionEngine(self.project_root, gemini, sd, True)
        self.exam_engine = ExamEngine(self.project_root, gemini)

    def _setup_ui(self):
        # 1. HEADER
        self.header_frame = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color="#1f2937")
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.lbl_tutor_info = ctk.CTkLabel(self.header_frame, text="Luna Tutor System", font=("Helvetica", 14, "bold"),
                                           text_color="white")
        self.lbl_tutor_info.pack(side="left", padx=20, pady=5)

        self.btn_exam = ctk.CTkButton(self.header_frame, text="MODALITÀ ESAME", width=120, height=28,
                                      fg_color="#b91c1c", command=self.start_exam_mode)
        self.btn_exam.pack(side="right", padx=10)

        self.btn_save = ctk.CTkButton(self.header_frame, text="💾 SALVA", width=80, height=28, fg_color="#374151",
                                      command=self.save_game)
        self.btn_save.pack(side="right", padx=5)

        self.btn_load = ctk.CTkButton(self.header_frame, text="📂 CARICA", width=80, height=28, fg_color="#374151",
                                      command=self.load_game)
        self.btn_load.pack(side="right", padx=5)

        # 2. LEFT PANEL
        self.left_panel = ctk.CTkFrame(self, fg_color="#000000", corner_radius=0)
        self.left_panel.grid(row=1, column=0, sticky="nsew")

        self.image_label = ctk.CTkLabel(self.left_panel, text="", cursor="hand2")
        self.image_label.place(relx=0.5, rely=0.5, anchor="center")
        self.image_label.bind("<Button-1>", self.open_image_viewer)

        self.loading_label = ctk.CTkLabel(self.left_panel, text="In attesa...", text_color="#10b981",
                                          font=("Helvetica", 14))
        self.loading_label.place(relx=0.5, rely=0.9, anchor="center")
        self.progress_bar = ctk.CTkProgressBar(self.left_panel, width=300, mode="indeterminate",
                                               progress_color="#10b981")

        # 3. RIGHT PANEL
        self.right_panel = ctk.CTkFrame(self, fg_color="#111827", corner_radius=0)
        self.right_panel.grid(row=1, column=1, sticky="nsew")
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=0)
        self.right_panel.grid_rowconfigure(2, weight=0)
        self.right_panel.grid_columnconfigure(0, weight=1)

        self.text_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.text_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        self.question_text = ctk.CTkTextbox(self.text_frame, font=("Helvetica", 16), text_color="#e5e7eb", wrap="word",
                                            fg_color="#1f2937", corner_radius=10)
        self.question_text.pack(fill="both", expand=True)
        self.question_text.configure(state="disabled")

        self.options_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.options_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))

        self.btn_options = {}
        for l in ["A", "B", "C", "D"]:
            self.btn_options[l] = ctk.CTkButton(self.options_frame, text=l, height=90, anchor="w",
                                                font=("Helvetica", 14), fg_color="#374151", hover_color="#4b5563",
                                                command=lambda x=l: self.submit_answer(x))

        self.btn_next = ctk.CTkButton(self.options_frame, text="AVANTI ➤", height=50,
                                      font=("Helvetica", 15, "bold"), fg_color="#059669",
                                      command=self.next_step_action)

        self.input_frame = ctk.CTkFrame(self.right_panel, height=60, fg_color="#1f2937", corner_radius=0)
        self.input_frame.grid(row=2, column=0, sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.entry_msg = ctk.CTkEntry(self.input_frame, placeholder_text="Fai una domanda al Tutor...", height=40,
                                      fg_color="#374151", border_width=0, text_color="white")
        self.entry_msg.grid(row=0, column=0, padx=(20, 10), pady=10, sticky="ew")
        self.entry_msg.bind("<Return>", lambda e: self.send_message())

        self.btn_send = ctk.CTkButton(self.input_frame, text="INVIA", width=80, height=40, fg_color="#059669",
                                      command=self.send_message)
        self.btn_send.grid(row=0, column=1, padx=(0, 20), pady=10)

    def set_text(self, content):
        self.question_text.configure(state="normal")
        self.question_text.delete("0.0", "end")
        self.question_text.insert("0.0", content)
        self.question_text.configure(state="disabled")

    def save_game(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Salvataggio Luna", "*.json")])
        if file_path:
            self.engine.save_session_to_file(self.session_state, file_path)
            messagebox.showinfo("Salvataggio", "Partita salvata!")

    def load_game(self):
        file_path = filedialog.askopenfilename(filetypes=[("Salvataggio Luna", "*.json")])
        if file_path:
            ns = self.engine.load_session_from_file(file_path)
            if ns:
                self.session_state = ns
                self.show_summary_screen()

    def show_summary_screen(self):
        stop()
        self.step = "summary"
        self.set_ui_ready()

        for b in self.btn_options.values(): b.pack_forget()
        self.btn_next.pack_forget()

        lessons = self.session_state.completed_lessons
        if not lessons:
            summary = "Nessuna lezione completata finora."
        else:
            summary = "📜 REGISTRO LEZIONI COMPLETATE:\n\n"
            for l in lessons:
                icon = "✅" if l.score >= 8 else "❌"
                summary += f"{icon} {l.topic} (Tutor: {l.tutor}) - Voto: {l.score}/10\n"
                if l.score >= 8:
                    summary += "   (Superato - Non verrà ripetuto)\n\n"
                else:
                    summary += "   (Insufficiente - Da ripassare)\n\n"

        self.lbl_tutor_info.configure(text="RIEPILOGO CARRIERA")
        self.set_text(summary)

        self.btn_next.configure(text="INIZIA NUOVA LEZIONE (Argomenti Nuovi) ➤", command=self.start_new_block)
        self.btn_next.pack(fill="x", pady=20)

    def start_new_block(self):
        stop()
        self.step = "lesson"
        self.set_ui_loading("Generazione Lezione & Immagine...")
        threading.Thread(target=self._gen_lesson_thread, daemon=True).start()

    def _gen_lesson_thread(self):
        text, img_path = self.engine.start_new_lesson_block(self.session_state)
        self.after(0, lambda: self._show_lesson(text, img_path))

    def _show_lesson(self, text, img_path):
        self.set_ui_ready()
        tutor = self.session_state.current_tutor
        topic = self.session_state.current_topic

        self.lbl_tutor_info.configure(text=f"DOCENTE: {tutor} | ARGOMENTO: {topic}")
        self.set_text(f"🎓 LEZIONE MAGISTRALE\n\n{text}")
        if img_path: self._load_image(img_path)

        for b in self.btn_options.values(): b.pack_forget()
        self.btn_next.configure(text="TUTTO CHIARO - INIZIA QUIZ (10 Domande) ➤", command=self.start_quiz_loop)
        self.btn_next.pack(fill="x", pady=5)
        speak(f"Lezione su {topic}. {text}", tutor=tutor)

    def start_quiz_loop(self):
        self.step = "quiz"
        self.next_quiz_question()

    def next_quiz_question(self):
        stop()
        if self.session_state.quiz_counter >= 10:
            self.show_final_report()
            return
        idx = self.session_state.quiz_counter + 1
        self.set_ui_loading(f"Caricamento Quiz {idx}/10...")
        threading.Thread(target=self._gen_quiz_thread, daemon=True).start()

    def _gen_quiz_thread(self):
        q = self.engine.get_next_quiz_question(self.session_state)
        self.after(0, lambda: self._show_quiz_question(q))

    def _show_quiz_question(self, q):
        self.set_ui_ready()
        self.current_question = q
        self.can_answer = True
        idx = self.session_state.quiz_counter + 1
        score = self.session_state.quiz_score
        self.lbl_tutor_info.configure(text=f"QUIZ {idx}/10 | Punteggio: {score} | Tutor: {q.tutor}")
        self.set_text(f"❓ DOMANDA\n\n{q.domanda}")
        self.btn_next.pack_forget()
        for l in ["A", "B", "C", "D"]:
            raw = q.opzioni.get(l, "-")
            wrap = "\n".join(textwrap.wrap(raw, width=45))
            self.btn_options[l].configure(text=f"{l}) {wrap}", state="normal", fg_color="#374151")
            self.btn_options[l].pack(fill="x", pady=5)
        speak(q.domanda, tutor=q.tutor)

    def submit_answer(self, choice):
        if not self.can_answer: return
        stop()
        self.can_answer = False
        self.set_ui_loading("Verifica...")
        threading.Thread(target=self._process_answer_thread, args=(choice,), daemon=True).start()

    def _process_answer_thread(self, choice):
        res = self.engine.apply_answer(self.session_state, self.current_question, choice)
        fb = self.engine.get_answer_feedback(self.current_question, res.outcome, res.new_stage)
        img = self.engine.last_image_path
        self.after(0, lambda: self._show_feedback(res, fb, img))

    def _show_feedback(self, res, fb, img):
        self.set_ui_ready()
        for b in self.btn_options.values(): b.pack_forget()
        icon = "✅" if res.outcome == "corretta" else "❌"
        spieg = getattr(self.current_question, "spiegazione_breve", "")
        corr_clean = self.current_question.corretta.strip().upper()
        if len(corr_clean) > 1: corr_clean = corr_clean[0]
        full_text = f"{fb}\n\n{icon} RISPOSTA {res.outcome.upper()}\n\n✅ Corretta: {corr_clean}\n\n📖 Spiegazione:\n{spieg}"
        self.set_text(full_text)
        if img: self._load_image(img)
        speak(f"{fb}. {spieg}", tutor=self.current_question.tutor)
        lbl = "PROSSIMA DOMANDA ➤" if self.session_state.quiz_counter < 10 else "VAI ALLA PAGELLA ➤"
        self.btn_next.configure(text=lbl, command=self.next_quiz_question)
        self.btn_next.pack(fill="x", pady=5)

    def show_final_report(self):
        self.step = "report"
        self.set_ui_loading("Elaborazione Pagella...")
        threading.Thread(target=self._gen_report_thread, daemon=True).start()

    def _gen_report_thread(self):
        rep = self.engine.generate_final_report(self.session_state)
        self.after(0, lambda: self._display_report(rep))

    def _display_report(self, text):
        self.set_ui_ready()
        score = self.session_state.quiz_score
        self.set_text(f"📊 PAGELLA FINALE\n\nPunteggio Totale: {score}/10\n\n{text}")
        self.btn_next.configure(text="NUOVA LEZIONE (Argomento Casuale) ➤", command=self.start_new_block)
        self.btn_next.pack(fill="x", pady=5)
        tutor = self.session_state.current_tutor
        speak(f"Hai fatto {score} su 10. {text}", tutor=tutor)

    def set_ui_loading(self, text):
        self.loading_label.configure(text=text)
        self.progress_bar.place(relx=0.5, rely=0.5, anchor="center")
        self.progress_bar.start()

    def set_ui_ready(self):
        self.progress_bar.stop()
        self.progress_bar.place_forget()
        self.loading_label.configure(text="")

    def next_step_action(self):
        pass

    def send_message(self):
        txt = self.entry_msg.get()
        if not txt: return
        self.entry_msg.delete(0, "end")
        self.question_text.configure(state="normal")
        self.question_text.insert("end", f"\n\n👤 TU: {txt}\n")
        self.question_text.see("end")
        self.question_text.configure(state="disabled")
        threading.Thread(target=self._chat_thread, args=(txt,), daemon=True).start()

    def _chat_thread(self, txt):
        tutor = self.session_state.current_tutor or "Luna"
        stage = self.session_state.stage.get(tutor, 1)
        q = type('', (), {})()
        q.tutor = tutor
        q.domanda = "Lesson Context"
        resp = self.engine.get_tutor_response(q, txt, False, stage)
        self.after(0, lambda: self._update_chat(resp, tutor))

    def _update_chat(self, txt, tutor):
        self.question_text.configure(state="normal")
        self.question_text.insert("end", f"\n👩‍🏫 {tutor}: {txt}\n")
        self.question_text.see("end")
        self.question_text.configure(state="disabled")
        speak(txt, tutor=tutor)

    def _load_image(self, path):
        # FIX: Aggiorna self.last_image_path così il popup funziona!
        self.last_image_path = path
        try:
            pil = Image.open(path)
            target_w = 450
            ratio = target_w / pil.width
            target_h = int(pil.height * ratio)
            if target_h > 800:
                target_h = 800
                target_w = int(pil.width * (800 / pil.height))
            ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(target_w, target_h))
            self.image_label.configure(image=ctk_img)
            self.image_label.image = ctk_img
        except Exception as e:
            print(f"Errore caricamento immagine: {e}")

    def open_image_viewer(self, e):
        if self.last_image_path: ImagePopup(self.last_image_path, self)

    def start_exam_mode(self):
        pass

    def on_close(self):
        shutdown_narrator()
        self.destroy()


if __name__ == "__main__":
    app = LunaGuiApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()