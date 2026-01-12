from xmlrpc.server import SimpleXMLRPCServer
import pika
import threading

# Configuração do RabbitMQ
RABBIT_HOST = 'localhost'

class ServidorChat:
    def __init__(self):
        # Banco de dados em memória
        self.usuarios = []       # Lista de nomes
        self.amigos = {}         # Dicionário { 'joao': ['maria', 'pedro'] }
        self.status = {}         # Dicionário { 'joao': 'online' }
        
        # Conexão persistente com RabbitMQ para criar filas e enviar mensagens
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(RABBIT_HOST))
        self.channel = self.connection.channel()
        print("Servidor conectado ao RabbitMQ e pronto via RPC.")

    # --- REQ 7: Criar fila ao entrar ---
    def registrar_usuario(self, nome):
        if nome not in self.usuarios:
            self.usuarios.append(nome)
            self.amigos[nome] = []
            self.status[nome] = 'offline'
            
            # Cria a fila exclusiva para este usuário no RabbitMQ
            self.channel.queue_declare(queue=f'fila_{nome}', durable=True)
            print(f"Usuário {nome} registrado e fila 'fila_{nome}' criada.")
            return True
        return True # Já existe, só retorna ok

    # --- REQ 2: Mudar estado ---
    def mudar_status(self, nome, novo_status):
        # status pode ser 'online' ou 'offline'
        if nome in self.usuarios:
            self.status[nome] = novo_status
            print(f"{nome} agora está {novo_status}")
            return True
        return False

    # --- REQ 8: Gestão de Contatos ---
    def adicionar_amigo(self, eu, nome_amigo):
        if eu in self.usuarios and nome_amigo in self.usuarios:
            if nome_amigo not in self.amigos[eu]:
                self.amigos[eu].append(nome_amigo)
                # Adiciona reciprocamente para facilitar teste
                if eu not in self.amigos[nome_amigo]:
                    self.amigos[nome_amigo].append(eu)
                return f"{nome_amigo} adicionado!"
        return "Erro: Usuário não encontrado."

    def listar_amigos(self, nome):
        return self.amigos.get(nome, [])

    # --- REQ 3, 4, 5 e 6: Envio de Mensagem ---
    def enviar_mensagem(self, remetente, destinatario, texto):
        if destinatario not in self.usuarios:
            return False
        
        # Monta a mensagem
        msg_corpo = f"[{remetente}]: {texto}"
        
        # A MÁGICA: Independente se está online ou offline, mandamos para a fila.
        # Se estiver Online, o cliente consome na hora (Req 3).
        # Se estiver Offline, fica guardado na fila (Req 4 e 6).
        self.channel.basic_publish(
            exchange='',
            routing_key=f'fila_{destinatario}',
            body=msg_corpo,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Mensagem persistente
            )
        )
        print(f"Mensagem de {remetente} enviada para a fila de {destinatario}")
        return True

# Inicializa o Servidor RPC na porta 8000
server = SimpleXMLRPCServer(("localhost", 8000), allow_none=True)
server.register_instance(ServidorChat())
print("Servidor RPC rodando na porta 8000...")
server.serve_forever()