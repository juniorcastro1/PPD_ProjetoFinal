import customtkinter as ctk
from tkinter import messagebox
import datetime
import pika
import threading
import json
import xmlrpc.client # Necessário para falar com o servidor RPC

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Conexão RPC com o Servidor (Para comandos como Adicionar/Remover)
        self.rpc_server = xmlrpc.client.ServerProxy("http://localhost:8000")

        # Variáveis de Estado
        self.is_connected = False
        self.connection = None
        self.channel = None
        self.consume_thread = None
        self.stop_thread = False

        self.title("Mensageiro com Confirmação")
        self.geometry("900x600")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================= SIDEBAR =================
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Painel", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.entry_identity = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Seu Nome")
        self.entry_identity.grid(row=2, column=0, padx=20, pady=(5, 10))

        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Status: OFFLINE", text_color="red")
        self.status_label.grid(row=3, column=0, padx=20, pady=(10, 0))

        self.btn_connect = ctk.CTkButton(self.sidebar_frame, text="Conectar", command=self.toggle_connection)
        self.btn_connect.grid(row=4, column=0, padx=20, pady=10)

        # --- Área de Contatos ---
        self.lbl_dest = ctk.CTkLabel(self.sidebar_frame, text="Contatos:", anchor="w")
        self.lbl_dest.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="n")
        
        self.users_list_dropdown = [] 
        self.user_dropdown = ctk.CTkOptionMenu(self.sidebar_frame, values=self.users_list_dropdown)
        self.user_dropdown.grid(row=7, column=0, padx=20, pady=(5, 10), sticky="n")

        # Botão Adicionar
        self.btn_add_user = ctk.CTkButton(self.sidebar_frame, text="+ Adicionar", width=100,
                                          fg_color="transparent", border_width=1, 
                                          command=self.request_new_friend)
        self.btn_add_user.grid(row=8, column=0, padx=20, pady=(0, 10), sticky="n")

        # Botão Remover (NOVO)
        self.btn_remove_user = ctk.CTkButton(self.sidebar_frame, text="- Remover", width=100,
                                             fg_color="transparent", border_width=1, text_color="red", hover_color="#550000",
                                             command=self.remove_current_friend)
        self.btn_remove_user.grid(row=9, column=0, padx=20, pady=(0, 20), sticky="n")

        # ================= CHAT =================
        self.chat_display = ctk.CTkTextbox(self, width=250)
        self.chat_display.grid(row=0, column=1, padx=(20, 20), pady=(20, 0), sticky="nsew")
        self.chat_display.configure(state="disabled")

        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=1, column=1, padx=20, pady=20, sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.entry_msg = ctk.CTkEntry(self.input_frame, placeholder_text="Conecte-se para iniciar...")
        self.entry_msg.grid(row=0, column=0, padx=(0, 20), sticky="ew")
        self.entry_msg.bind("<Return>", self.send_message)
        
        self.btn_send = ctk.CTkButton(self.input_frame, text="Enviar", command=self.send_message_event)
        self.btn_send.grid(row=0, column=1)

    # ================= LÓGICA =================

    def start_listening(self, my_queue):
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            channel = connection.channel()
            channel.queue_declare(queue=my_queue, durable=True)

            def callback(ch, method, properties, body):
                if self.stop_thread:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    channel.stop_consuming()
                    return 
                
                try:
                    payload = json.loads(body.decode())
                    msg_type = payload.get("type", "msg")
                    sender = payload.get("sender", "Desconhecido")

                    # --- LÓGICA DOS TIPOS DE MENSAGEM ---
                    if msg_type == "invite":
                        # Recebeu convite: Mostra popup na Thread Principal
                        self.after(0, lambda: self.handle_invite(sender))
                    
                    elif msg_type == "confirmacao":
                        # Alguém aceitou seu convite
                        self.after(0, lambda: self.add_contact_local(sender))
                        self.after(0, lambda: self.log_to_chat_system(f"🎉 {sender} aceitou seu pedido de amizade!"))

                    elif msg_type == "msg":
                        # Mensagem normal de chat
                        content = payload.get("content", "")
                        display_text = f"{sender}: {content}"
                        self.after(0, lambda: self.log_to_chat_received(display_text))

                except Exception as e:
                    print(f"Erro decodificando msg: {e}")
                
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=my_queue, on_message_callback=callback, auto_ack=False)
            channel.start_consuming()

        except Exception as e:
            print(f"Erro na thread: {e}")

    # --- Funções de Amizade ---

    def request_new_friend(self):
        """Pede nome e manda solicitação via RPC"""
        if not self.is_connected:
            messagebox.showerror("Erro", "Conecte-se primeiro.")
            return

        dialog = ctk.CTkInputDialog(text="Nome do usuário para adicionar:", title="Adicionar Amigo")
        target_user = dialog.get_input()
        
        if target_user:
            my_id = self.entry_identity.get()
            try:
                # Chama o servidor RPC para enviar o convite
                resposta = self.rpc_server.solicitar_amizade(my_id, target_user)
                messagebox.showinfo("Status", resposta)
            except Exception as e:
                messagebox.showerror("Erro RPC", str(e))

    def handle_invite(self, sender_name):
        """Chamado quando chega msg do tipo 'invite'"""
        aceitar = messagebox.askyesno("Pedido de Amizade", f"O usuário '{sender_name}' quer te adicionar.\nAceitar?")
        
        if aceitar:
            my_id = self.entry_identity.get()
            try:
                # Confirma no servidor (que cria o vínculo e avisa o outro)
                sucesso = self.rpc_server.aceitar_amizade(my_id, sender_name)
                if sucesso:
                    self.add_contact_local(sender_name)
                    self.log_to_chat_system(f"Você aceitou {sender_name}.")
            except Exception as e:
                print(f"Erro ao aceitar: {e}")

    def remove_current_friend(self):
        """Remove o amigo selecionado no dropdown"""
        if not self.is_connected: return
        
        target = self.user_dropdown.get()
        if not target or target not in self.users_list_dropdown:
            messagebox.showwarning("Atenção", "Selecione um contato válido para remover.")
            return
            
        confirm = messagebox.askyesno("Confirmar", f"Tem certeza que deseja remover '{target}'?")
        if confirm:
            my_id = self.entry_identity.get()
            try:
                self.rpc_server.remover_amigo(my_id, target)
                
                # Remove localmente
                self.users_list_dropdown.remove(target)
                self.user_dropdown.configure(values=self.users_list_dropdown)
                if self.users_list_dropdown:
                    self.user_dropdown.set(self.users_list_dropdown[0])
                else:
                    self.user_dropdown.set("")
                
                self.log_to_chat_system(f"Contato '{target}' removido.")
            except Exception as e:
                messagebox.showerror("Erro RPC", str(e))

    def add_contact_local(self, nome):
        """Atualiza o dropdown (UI)"""
        if nome not in self.users_list_dropdown:
            self.users_list_dropdown.append(nome)
            self.user_dropdown.configure(values=self.users_list_dropdown)
            self.user_dropdown.set(nome)

    # --- Conexão e Envio ---

    def toggle_connection(self):
        my_id = self.entry_identity.get().strip()
        if not my_id: return

        if not self.is_connected:
            try:
                # Registra no servidor RPC
                self.rpc_server.registrar_usuario(my_id)
                
                # Conecta no RabbitMQ (Apenas para enviar msgs de chat direto)
                self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
                self.channel = self.connection.channel()
                
                self.stop_thread = False
                self.consume_thread = threading.Thread(target=self.start_listening, args=(my_id,))
                self.consume_thread.daemon = True
                self.consume_thread.start()

                self.is_connected = True
                self.status_label.configure(text="Status: ONLINE", text_color="#2CC985")
                self.btn_connect.configure(text="Desconectar", fg_color="#C0392B", hover_color="#E74C3C")
                self.entry_identity.configure(state="disabled")
                self.entry_msg.configure(state="normal", placeholder_text=f"Mensagem de {my_id}...")
                
                self.log_to_chat_system(f"Conectado como: {my_id}")

            except Exception as e:
                messagebox.showerror("Erro", f"Falha na conexão: {e}")
        else:
            self.stop_thread = True
            if self.connection: self.connection.close()
            self.is_connected = False
            self.status_label.configure(text="Status: OFFLINE", text_color="red")
            self.btn_connect.configure(text="Conectar", fg_color=["#3B8ED0", "#1F6AA5"])
            self.entry_identity.configure(state="normal")
            self.entry_msg.configure(state="disabled")

    def send_message_event(self):
        self.send_message(None)

    def send_message(self, event):
        if not self.is_connected: return
        msg = self.entry_msg.get()
        target = self.user_dropdown.get()
        my_id = self.entry_identity.get()
        
        if msg and target:
            # Envia via RPC (para validar amizade no servidor) ou direto no RabbitMQ
            # Opção: Vamos usar o RPC enviar_mensagem do servidor para garantir consistência
            try:
                self.rpc_server.enviar_mensagem(my_id, target, msg)
                self.log_to_chat_system(f"Eu -> {target}: {msg}")
                self.entry_msg.delete(0, "end")
            except Exception as e:
                self.log_to_chat_system(f"Erro envio: {e}")

    def log_to_chat_received(self, text):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"[{datetime.datetime.now().strftime('%H:%M')}] {text}\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def log_to_chat_system(self, text):
        self.log_to_chat_received(text)

if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()