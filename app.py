import customtkinter as ctk
from tkinter import messagebox
import datetime
import pika
import threading
import json

# --- Configurações Visuais ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Variáveis de Estado
        self.is_connected = False
        self.connection = None
        self.channel = None
        self.consume_thread = None
        self.stop_thread = False

        # Configuração da Janela Principal
        self.title("Mensageiro")
        self.geometry("900x600")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================= SIDEBAR =================
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Painel de Controle", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.lbl_identity = ctk.CTkLabel(self.sidebar_frame, text="Seu Nome", anchor="w")
        self.lbl_identity.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")

        self.entry_identity = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Ex: Fulano")
        self.entry_identity.grid(row=2, column=0, padx=20, pady=(5, 10))

        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Status: OFFLINE", text_color="red", font=ctk.CTkFont(weight="bold"))
        self.status_label.grid(row=3, column=0, padx=20, pady=(10, 0))

        self.btn_connect = ctk.CTkButton(self.sidebar_frame, text="Conectar", command=self.toggle_connection)
        self.btn_connect.grid(row=4, column=0, padx=20, pady=10)

        self.separator = ctk.CTkLabel(self.sidebar_frame, text="-------------------", text_color="gray")
        self.separator.grid(row=5, column=0, pady=5)

        self.lbl_dest = ctk.CTkLabel(self.sidebar_frame, text="Enviar para:", anchor="w")
        self.lbl_dest.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="n")
        
        self.users_list_dropdown = [] 
        self.user_dropdown = ctk.CTkOptionMenu(self.sidebar_frame, values=self.users_list_dropdown)
        self.user_dropdown.grid(row=7, column=0, padx=20, pady=(5, 10), sticky="n")

        self.btn_add_user = ctk.CTkButton(self.sidebar_frame, text="+ Adicionar Usuário", 
                                          fg_color="transparent", border_width=1, 
                                          command=self.add_new_user_dialog)
        self.btn_add_user.grid(row=8, column=0, padx=20, pady=(0, 20), sticky="n")

        # ================= ÁREA DO CHAT =================
        self.chat_display = ctk.CTkTextbox(self, width=250)
        self.chat_display.grid(row=0, column=1, padx=(20, 20), pady=(20, 0), sticky="nsew")
        self.chat_display.configure(state="disabled")

        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=1, column=1, padx=20, pady=20, sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.entry_msg = ctk.CTkEntry(self.input_frame, placeholder_text="Conecte-se para iniciar...")
        self.entry_msg.grid(row=0, column=0, padx=(0, 20), sticky="ew")
        
        self.entry_msg.bind("<Return>", self.send_message)
        self.entry_msg.configure(state="disabled")

        self.btn_send = ctk.CTkButton(self.input_frame, text="Enviar", command=self.send_message_event)
        self.btn_send.grid(row=0, column=1)
        self.btn_send.configure(state="disabled")

    # ================= LÓGICA DO SISTEMA =================

    def verificar_existencia_real(self, queue_name):
        if not self.is_connected: return False
        try:
            temp_channel = self.connection.channel()
            # Verifica passivamente (não cria, só checa)
            temp_channel.queue_declare(queue=queue_name, passive=True)
            temp_channel.close()
            return True
        except Exception:
            return False

    def start_listening(self, my_queue):
        """Thread que consome mensagens da fila DURÁVEL"""
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            channel = connection.channel()
            
            # [MODIFICAÇÃO 1] Fila Durable=True
            channel.queue_declare(queue=my_queue, durable=True)

            def callback(ch, method, properties, body):
                if self.stop_thread:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    channel.stop_consuming()
                    return
                
                try:
                    msg_data = json.loads(body.decode())
                    sender_name = msg_data.get("sender", "Desconhecido")
                    text_content = msg_data.get("content", "")
                    display_text = f"{sender_name}: {text_content}"
                except json.JSONDecodeError:
                    display_text = f"Recebido: {body.decode()}"
                
                self.after(0, lambda: self.log_to_chat_received(display_text))

                # [MODIFICAÇÃO 2] Confirmação manual (ACK)
                # Garante que a mensagem só saia da fila após ser processada
                ch.basic_ack(delivery_tag=method.delivery_tag)

            # auto_ack=False para usarmos a confirmação manual acima
            channel.basic_consume(queue=my_queue, on_message_callback=callback, auto_ack=False)
            channel.start_consuming()

        except Exception as e:
            print(f"Erro na thread: {e}")

    def toggle_connection(self):
        my_id = self.entry_identity.get().strip()

        if not my_id:
            messagebox.showwarning("Atenção", "Por favor, defina seu nome antes de conectar.")
            return

        if not self.is_connected:
            try:
                self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
                self.channel = self.connection.channel()
                
                # [MODIFICAÇÃO 3] Declara a PRÓPRIA fila como Durable=True ao conectar
                self.channel.queue_declare(queue=my_id, durable=True)
                
                self.stop_thread = False
                self.consume_thread = threading.Thread(target=self.start_listening, args=(my_id,))
                self.consume_thread.daemon = True
                self.consume_thread.start()

                self.is_connected = True
                self.status_label.configure(text="Status: ONLINE", text_color="#2CC985")
                self.btn_connect.configure(text="Desconectar", fg_color="#C0392B", hover_color="#E74C3C")
                self.entry_identity.configure(state="disabled")
                self.entry_msg.configure(state="normal", placeholder_text=f"Mensagem de {my_id}...")
                self.btn_send.configure(state="normal")
                
                self.log_to_chat_system(f"Conectado como: {my_id}")

            except Exception as e:
                messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao servidor.\n{e}")

        else:
            self.stop_thread = True
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            
            self.is_connected = False
            self.status_label.configure(text="Status: OFFLINE", text_color="red")
            self.btn_connect.configure(text="Conectar", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])
            self.entry_identity.configure(state="normal")
            self.entry_msg.configure(state="disabled", placeholder_text="Conecte-se para iniciar...")
            self.btn_send.configure(state="disabled")
            self.log_to_chat_system("Desconectado.")

    def add_new_user_dialog(self):
        if not self.is_connected:
            messagebox.showerror("Erro", "Conecte-se primeiro para buscar usuários.")
            return

        dialog = ctk.CTkInputDialog(text="Nome exato do usuário:", title="Adicionar Contato")
        new_user = dialog.get_input()
        
        if new_user:
            # Verifica se a fila existe (agora busca por filas duráveis também)
            existe = self.verificar_existencia_real(new_user)
            if existe:
                if new_user not in self.users_list_dropdown:
                    self.users_list_dropdown.append(new_user)
                    self.user_dropdown.configure(values=self.users_list_dropdown)
                    self.user_dropdown.set(new_user)
                    self.log_to_chat_system(f"Contato '{new_user}' adicionado.")
                else:
                    messagebox.showinfo("Info", "Usuário já está na lista.")
            else:
                messagebox.showerror("Não encontrado", f"O usuário '{new_user}' não tem uma fila criada no servidor.")

    def send_message_event(self):
        self.send_message(None)

    def send_message(self, event):
        if not self.is_connected: return

        message = self.entry_msg.get()
        target_queue = self.user_dropdown.get()
        my_id = self.entry_identity.get()
        
        if message:
            try:
                payload = {
                    "sender": my_id,
                    "content": message
                }
                
                # [MODIFICAÇÃO 4] Mensagem Persistente (delivery_mode=2)
                self.channel.basic_publish(
                    exchange='',
                    routing_key=target_queue,
                    body=json.dumps(payload),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Salva no disco
                    )
                )
                
                self.log_to_chat_system(f"Eu -> {target_queue}: {message}")
                self.entry_msg.delete(0, "end")
            except Exception as e:
                self.log_to_chat_system(f"ERRO ao enviar: {e}")

    def log_to_chat_received(self, text):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"[{timestamp}] {text}\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def log_to_chat_system(self, text):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"[{timestamp}] {text}\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()