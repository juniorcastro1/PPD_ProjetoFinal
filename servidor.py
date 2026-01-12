from xmlrpc.server import SimpleXMLRPCServer
import pika
import json

RABBIT_HOST = 'localhost'

class ServidorChat:
    def __init__(self):
        self.usuarios = []
        self.amigos = {} 
        
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(RABBIT_HOST))
        self.channel = self.connection.channel()
        print("Servidor conectado ao RabbitMQ e pronto via RPC.")

    def registrar_usuario(self, nome):
        if nome not in self.usuarios:
            self.usuarios.append(nome)
            self.amigos[nome] = []
            self.channel.queue_declare(queue=nome, durable=True)
            print(f"Usuário {nome} registrado.")
            return True
        return True

    def solicitar_amizade(self, eu, nome_amigo):
        if nome_amigo not in self.usuarios:
            return "Usuário não encontrado."
        
        if nome_amigo in self.amigos.get(eu, []):
            return "Vocês já são amigos."

        payload = {
            "type": "invite",
            "sender": eu
        }
        self.channel.basic_publish(
            exchange='',
            routing_key=nome_amigo,
            body=json.dumps(payload),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        return "Solicitação enviada com sucesso!"

    def aceitar_amizade(self, eu, novo_amigo):
        if eu not in self.amigos: self.amigos[eu] = []
        if novo_amigo not in self.amigos: self.amigos[novo_amigo] = []

        if novo_amigo not in self.amigos[eu]:
            self.amigos[eu].append(novo_amigo)
            self.amigos[novo_amigo].append(eu)
            
            payload = {
                "type": "confirmacao",
                "sender": eu
            }
            self.channel.basic_publish(
                exchange='',
                routing_key=novo_amigo,
                body=json.dumps(payload),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            print(f"Amizade formada: {eu} <-> {novo_amigo}")
            return True
        return False

    def remover_amigo(self, eu, ex_amigo):
        removido = False
        # Remove do solicitante
        if eu in self.amigos and ex_amigo in self.amigos[eu]:
            self.amigos[eu].remove(ex_amigo)
            removido = True
        
        # Remove do ex-amigo (recíproco)
        if ex_amigo in self.amigos and eu in self.amigos[ex_amigo]:
            self.amigos[ex_amigo].remove(eu)
        
        if removido:
            print(f"Amizade desfeita: {eu} -X- {ex_amigo}")
            
            # Avisa o ex-amigo que ele foi removido para atualizar a UI dele
            payload = {
                "type": "friend_removed",
                "sender": eu
            }
            self.channel.basic_publish(
                exchange='',
                routing_key=ex_amigo,
                body=json.dumps(payload),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            return True
        return False

    def enviar_mensagem(self, remetente, destinatario, texto):
        pass

server = SimpleXMLRPCServer(("localhost", 8000), allow_none=True)
server.register_instance(ServidorChat())
print("Servidor RPC rodando na porta 8000...")
server.serve_forever()