# Este módulo define os estados operacionais de uma cobrança dentro do sistema.
# Por meio desses status, é possível monitorar o andamento de cada processo de cobrança, registrar interações com os clientes e apoiar a tomada de decisão em relação a débitos pendentes, contribuindo para uma gestão mais eficiente e organizada.

STATUS_COBRANCA = [
    "pendente",
    "cliente_respondeu",
    "pago",
    "sem_resposta",
    "encaminhar_extrajudicial"
]