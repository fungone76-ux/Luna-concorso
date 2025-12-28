# src/gui_main.py
import os
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image
import customtkinter as ctk

from src.ai.gemini_client import GeminiClient
from src.visuals.sd_client import SDClient, SDConfig
from src.engine.session_engine import SessionEngine
from src.engine.exam_engine import ExamEngine
from src.domain.models import SessionState
# Importiamo i pesi per sapere il numero totale di materie (16)
from src.engine.subject_picker import DEFAULT_WEIGHTS

# Configurazione aspetto
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class StudyApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LUNA - Concorso MIC Assistant")
        self.geometry("1200x800")

        # --- SETUP ENGINE ---
        self.project_root = os.getcwd()

        # 1. Configura Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            messagebox.showwarning("Configurazione",
                                   "Manca GEMINI_API_KEY nelle variabili d'ambiente.\nIl gioco potrebbe non funzionare.")
            api_key = "DUMMY"

        self.gemini_client = GeminiClient(api_key=api_key)

        # 2. Configura SD (Opzionale)
        self.sd_config = SDConfig.from_env()
        self.sd_client = SDClient(self.sd_config)
        self.enable_sd = True  # Default ON

        # 3. Session Engine
        self.engine = SessionEngine(self.project_root, self.gemini_client, self.sd_client, self.enable_sd)

        # 4. Exam Engine
        self.exam_engine = ExamEngine(self.project_root, self.gemini_client)

        # 5. Stato
        self.state = SessionState()
        self.exam_session = None

        # Carica salvataggio se esiste
        save_path = os.path.join(self.project_root, "session_save.json")
        if os.path.exists(save_path):
            loaded = self.engine.load_session_from_file(save_path)
            if loaded:
                self.state = loaded
                print("Salvataggio caricato.")

        # --- GUI LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # Main Area
        self.main_area = ctk.CTkFrame(self, corner_radius=0)
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Inizializza viste
        self.show_home()

    def setup_sidebar(self):
        lbl_logo = ctk.CTkLabel(self.sidebar, text="LUNA\nSTUDY\nASSISTANT", font=ctk.CTkFont(size=20, weight="bold"))
        lbl_logo.pack(pady=40)

        btn_home = ctk.CTkButton(self.sidebar, text="Home / Stato", command=self.show_home)
        btn_home.pack(pady=10, padx=20, fill="x")

        btn_lesson = ctk.CTkButton(self.sidebar, text="Nuova Lezione", command=self.start_lesson_thread)
        btn_lesson.pack(pady=10, padx=20, fill="x")

        btn_exam = ctk.CTkButton(self.sidebar, text="Simulazione Esame", command=self.start_exam_mode,
                                 fg_color="#D32F2F", hover_color="#B71C1C")
        btn_exam.pack(pady=10, padx=20, fill="x")

        # Toggle SD
        self.sw_sd = ctk.CTkSwitch(self.sidebar, text="Immagini AI", command=self.toggle_sd)
        self.sw_sd.select()
        self.sw_sd.pack(pady=30, padx=20, side="bottom")

        btn_save = ctk.CTkButton(self.sidebar, text="Salva & Esci", command=self.save_and_exit, fg_color="green")
        btn_save.pack(pady=20, padx=20, side="bottom")

    def toggle_sd(self):
        self.enable_sd = bool(self.sw_sd.get())
        self.engine.enable_sd = self.enable_sd
        print(f"SD Enabled: {self.enable_sd}")

    def clear_main(self):
        for widget in self.main_area.winfo_children():
            widget.destroy()

    # --- VISTE ---

    def show_home(self):
        self.clear_main()

        # Titolo
        lbl = ctk.CTkLabel(self.main_area, text="Bentornato, Candidato.", font=ctk.CTkFont(size=24, weight="bold"))
        lbl.pack(pady=20)

        # --- SEZIONE PROGRESSO (NUOVA) ---
        progress_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        progress_frame.pack(fill="x", padx=40, pady=20)

        # Calcolo Progresso
        # Conta le materie uniche (pulendo i sotto-titoli) che hanno voto >= 8
        passed_unique = set()
        for lesson in self.state.completed_lessons:
            if lesson.score >= 8:
                # Esempio: "Diritto: Accesso atti" -> "Diritto"
                clean_topic = lesson.topic.split(":")[0].strip()
                passed_unique.add(clean_topic)

        # Totale materie (16)
        total_subjects = len(DEFAULT_WEIGHTS)
        completed_count = len(passed_unique)
        ratio = completed_count / total_subjects if total_subjects > 0 else 0

        # Etichetta Progresso
        lbl_prog = ctk.CTkLabel(
            progress_frame,
            text=f"Progresso Carriera: {completed_count}/{total_subjects} Materie Completate ({int(ratio * 100)}%)",
            font=ctk.CTkFont(size=16)
        )
        lbl_prog.pack(anchor="w", pady=(0, 5))

        # Barra
        progress_bar = ctk.CTkProgressBar(progress_frame, height=20)
        progress_bar.set(ratio)  # Valore da 0 a 1
        progress_bar.pack(fill="x")

        if ratio >= 1.0:
            progress_bar.configure(progress_color="#00FF00")  # Verde se finito
            ctk.CTkLabel(progress_frame, text="COMPLIMENTI! SEI PRONTO PER IL CONCORSO!", text_color="#00FF00").pack(
                pady=5)

        # --- SEZIONE STATISTICHE RAPIDE ---
        stats_frame = ctk.CTkFrame(self.main_area)
        stats_frame.pack(fill="both", expand=True, padx=40, pady=20)

        ctk.CTkLabel(stats_frame, text="Ultime Lezioni:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20,
                                                                                                pady=10)

        # Mostra ultime 5 lezioni
        recents = self.state.completed_lessons[-5:]
        if not recents:
            ctk.CTkLabel(stats_frame, text="Nessuna lezione completata.").pack(pady=10)
        else:
            for l in reversed(recents):
                color = "green" if l.score >= 8 else "orange" if l.score >= 6 else "red"
                txt = f"[{l.tutor}] {l.topic} -> Voto: {l.score}/10"
                ctk.CTkLabel(stats_frame, text=txt, text_color=color).pack(anchor="w", padx=20, pady=2)

    # --- LOGICA LEZIONE ---

    def start_lesson_thread(self):
        # Disabilita bottoni sidebar per evitare doppi click
        self.clear_main()
        lbl = ctk.CTkLabel(self.main_area, text="Generazione lezione in corso...\nAttendere prego (Gemini + SD)...",
                           font=ctk.CTkFont(size=18))
        lbl.pack(pady=50)

        pb = ctk.CTkProgressBar(self.main_area)
        pb.pack(pady=10)
        pb.start()

        threading.Thread(target=self._run_lesson_gen, daemon=True).start()

    def _run_lesson_gen(self):
        text, img_path = self.engine.start_new_lesson_block(self.state)
        # Ritorna al thread principale per aggiornare GUI
        self.after(0, lambda: self.show_lesson_page(text, img_path))

    def show_lesson_page(self, text, img_path):
        self.clear_main()

        # Split frame: Testo a sinistra, Immagine a destra (se c'è)
        container = ctk.CTkFrame(self.main_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        # Text Area
        txt_box = ctk.CTkTextbox(container, width=600, font=ctk.CTkFont(size=16))
        txt_box.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        txt_box.insert("0.0", text)
        txt_box.configure(state="disabled")

        # Image Area
        if img_path and os.path.exists(img_path):
            try:
                pil_img = Image.open(img_path)
                # Resize
                w_box = 400
                ratio = pil_img.height / pil_img.width
                h_box = int(w_box * ratio)
                my_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w_box, h_box))

                lbl_img = ctk.CTkLabel(container, image=my_image, text="")
                lbl_img.pack(side="right", padx=10, pady=10, anchor="n")
            except Exception as e:
                print(f"Errore caricamento immagine: {e}")

        # Bottone "Inizia Quiz"
        btn_quiz = ctk.CTkButton(self.main_area, text="SONO PRONTO: INIZIA QUIZ", height=50,
                                 command=self.start_quiz_flow, font=ctk.CTkFont(size=18, weight="bold"))
        btn_quiz.pack(fill="x", padx=50, pady=20)

    # --- LOGICA QUIZ (ALLENAMENTO) ---

    def start_quiz_flow(self):
        self.state.quiz_counter = 0
        self.state.quiz_score = 0
        self.state.quiz_results = []
        self.next_quiz_question()

    def next_quiz_question(self):
        # Se abbiamo fatto 3 domande, finiamo
        if self.state.quiz_counter >= 3:
            self.show_final_report()
            return

        self.clear_main()
        lbl_wait = ctk.CTkLabel(self.main_area, text="Generazione domanda...", font=ctk.CTkFont(size=18))
        lbl_wait.pack(pady=50)

        threading.Thread(target=self._fetch_question, daemon=True).start()

    def _fetch_question(self):
        q = self.engine.get_next_quiz_question(self.state)
        self.after(0, lambda: self.display_question(q))

    def display_question(self, question):
        self.clear_main()

        # Info header
        header = f"Domanda {self.state.quiz_counter + 1}/3 - {question.materia}"
        ctk.CTkLabel(self.main_area, text=header, text_color="gray").pack(pady=(10, 5))

        # Domanda
        q_box = ctk.CTkTextbox(self.main_area, height=100, fg_color="transparent",
                               font=ctk.CTkFont(size=18, weight="bold"))
        q_box.insert("0.0", question.domanda)
        q_box.configure(state="disabled")
        q_box.pack(fill="x", padx=20, pady=10)

        # Immagine (se c'è, magari generata dall'ultimo step, o nuova)
        # Per semplicità, qui non rigeneriamo l'immagine ad ogni domanda per velocità,
        # ma se vuoi si può fare. Mostriamo l'ultima generata se esiste.
        if self.engine.last_image_path and os.path.exists(self.engine.last_image_path):
            # Codice display immagine ridotto per brevità (simile a sopra)
            pass

        # Opzioni
        btns_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        btns_frame.pack(fill="both", expand=True, padx=50, pady=10)

        for letter in ["A", "B", "C", "D"]:
            text_opt = question.opzioni.get(letter, "...")
            btn = ctk.CTkButton(
                btns_frame,
                text=f"{letter}. {text_opt}",
                anchor="w",
                command=lambda l=letter: self.answer_chosen(question, l)
            )
            btn.pack(fill="x", pady=5)

    def answer_chosen(self, question, choice):
        # Valuta
        result = self.engine.apply_answer(self.state, question, choice)

        # Feedback popup o schermata
        msg = f"Risposta {result.outcome.upper()}!\n\nCorretta era: {question.corretta}"
        if result.outcome == "corretta":
            msg = "BRAVO! Risposta Esatta."

        messagebox.showinfo("Esito", msg)

        # Prossima
        self.next_quiz_question()

    def show_final_report(self):
        self.clear_main()
        lbl = ctk.CTkLabel(self.main_area, text="Generazione Pagella...", font=ctk.CTkFont(size=18))
        lbl.pack(pady=50)

        threading.Thread(target=self._gen_report, daemon=True).start()

    def _gen_report(self):
        txt = self.engine.generate_final_report(self.state)
        # Salva su disco automaticamente
        self.engine.save_session_to_file(self.state, os.path.join(self.project_root, "session_save.json"))
        self.after(0, lambda: self.display_report_text(txt))

    def display_report_text(self, text):
        self.clear_main()
        lbl = ctk.CTkLabel(self.main_area, text="PAGELLA FINALE", font=ctk.CTkFont(size=22, weight="bold"))
        lbl.pack(pady=10)

        txt_box = ctk.CTkTextbox(self.main_area, font=ctk.CTkFont(size=16))
        txt_box.pack(fill="both", expand=True, padx=20, pady=10)
        txt_box.insert("0.0", text)

        btn = ctk.CTkButton(self.main_area, text="Torna alla Home", command=self.show_home)
        btn.pack(pady=20)

    # --- LOGICA ESAME (SIMULAZIONE) ---
    def start_exam_mode(self):
        self.clear_main()
        # Avvia esame
        self.exam_session = self.exam_engine.start_exam()
        self.show_exam_question()

    def show_exam_question(self):
        q = self.exam_engine.get_next_question(self.exam_session)
        if not q:
            self.finish_exam()
            return

        self.clear_main()

        # Header Esame
        remaining = len(self.exam_session.subject_roadmap) - self.exam_session.current_index
        ctk.CTkLabel(self.main_area, text=f"SIMULAZIONE ESAME - Domanda {self.exam_session.current_index + 1}/40",
                     text_color="red").pack(pady=5)

        # Testo Domanda
        q_box = ctk.CTkTextbox(self.main_area, height=120, font=ctk.CTkFont(size=16))
        q_box.insert("0.0", q.domanda)
        q_box.configure(state="disabled")
        q_box.pack(fill="x", padx=20, pady=10)

        # Opzioni
        for letter in ["A", "B", "C", "D"]:
            val = q.opzioni.get(letter, ".")
            btn = ctk.CTkButton(self.main_area, text=f"{letter}) {val}", anchor="w",
                                command=lambda l=letter: self.submit_exam_answer(l))
            btn.pack(fill="x", padx=40, pady=5)

    def submit_exam_answer(self, choice):
        self.exam_engine.submit_answer(self.exam_session, choice)
        self.exam_session.current_index += 1
        self.show_exam_question()

    def finish_exam(self):
        score, passed, report = self.exam_engine.calculate_result(self.exam_session)

        self.clear_main()
        color = "green" if passed else "red"
        ctk.CTkLabel(self.main_area, text="ESITO ESAME", font=ctk.CTkFont(size=30, weight="bold"),
                     text_color=color).pack(pady=20)

        res_box = ctk.CTkTextbox(self.main_area, font=ctk.CTkFont(size=18))
        res_box.insert("0.0", report)
        res_box.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkButton(self.main_area, text="Chiudi Esame", command=self.show_home).pack(pady=20)

    def save_and_exit(self):
        self.engine.save_session_to_file(self.state, os.path.join(self.project_root, "session_save.json"))
        self.destroy()


if __name__ == "__main__":
    app = StudyApp()
    app.mainloop()