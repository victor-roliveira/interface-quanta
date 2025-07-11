import json

with open("credenciais.json", "r") as f:
    data = json.load(f)

# Escapa \n para \\\\n
data["private_key"] = data["private_key"].replace("\n", "\\n")

# Converte o dicionário para uma string JSON válida
json_string = json.dumps(data)

# Copie essa saída e cole nos secrets
print(json_string)
