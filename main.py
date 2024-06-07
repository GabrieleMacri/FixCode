from datetime import datetime
import os
import json
import sys
from git import Repo
import openai

# Carica la chiave API da un file JSON
with open("secrets.json") as f:
    secrets = json.load(f)
    api_key = secrets["api_key"]

# Imposta la chiave API per l'oggetto openai.api_key
openai.api_key = api_key

# Funzione per ottenere una risposta dall'API di OpenAI
def get_response(messages):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        temperature=1.0,
        messages=messages
    )
    return response.choices[0].message

# Funzione per leggere il contenuto da un file 

def read_file(filename):
    with open(filename, "r", encoding="utf-8") as file:
        content = file.read()
    return content

# Funzione per scrivere il contenuto in un file 
def write_file(filename, content):
    # Elimina il file esistente, se presente
    if os.path.exists(filename):
        os.remove(filename)
    
    # Crea il nuovo file con lo stesso nome e scrivi il contenuto
    with open(filename, "w", encoding="utf-8") as file:
        file.write(content)

def extract_value(chiave):
    # Leggi il file JSON
    with open('requests.json', 'r') as file:
        data = json.load(file)
    
    # Restituisci il valore associato alla chiave
    return data.get(chiave, "Chiave non trovata")

def search_files_by_extension(cartella, estensione):

    file_trovati = []

    # Converti il percorso della cartella in un percorso assoluto
    cartella_assoluta = os.path.abspath(cartella)

    # Verifica che la cartella esista
    if not os.path.isdir(cartella_assoluta):
        print(f"Errore: La cartella {cartella_assoluta} non esiste.")
        return []

    # Itera su tutti i file e le sottocartelle nella cartella specificata
    for root, dirs, files in os.walk(cartella_assoluta):
        # Controlla se 'test' è nel percorso corrente e salta questa iterazione se lo è
        if 'test' in root.split(os.sep):
            continue
        
        for file in files:
            if file.endswith(estensione):
                # Aggiungi il percorso completo del file alla lista
                file_trovati.append(os.path.join(root, file))
    
    return file_trovati


def elimina_righe_backtick(testo):
    righe = testo.split('\n')
    righe_da_mantenere = []
    for riga in righe:
        if not riga.startswith('`'):
            righe_da_mantenere.append(riga)
    testo_senza_backtick = '\n'.join(righe_da_mantenere)
    return testo_senza_backtick

def split_text_at_comment(text):
    # Split the text into lines
    lines = text.split('\n')
    
    # Initialize variables to hold the two parts of the text
    part1 = []
    part2 = []
    
    # Flag to indicate if the split point has been found
    found_comment = False
    
    # Iterate through each line
    for line in lines:
        if "Comment" in line:
            found_comment = True
        elif found_comment:
            part2.append(line)
        else:
            part1.append(line)
    
    # Join the parts back into single strings
    part1_text = '\n'.join(part1)
    part2_text = '\n'.join(part2)
    
    return part1_text, part2_text



def fix_file(cartella, estensione, repo_path):

    file_trovati = search_files_by_extension(cartella, estensione)
        
    text_extensions = extract_value(estensione)
    
    
    # Crea un messaggio con il testo estratto dal file 


    for text in file_trovati:
        # Leggi il file e ottieni il testo
        text_content = read_file(text)
        
        messages = [
        {"role": "system", "content": text_extensions},
        ]
        
        # Crea un messaggio con il testo estratto dal file 
        message = {"role": "user", "content": text_content}
        
        # Aggiungi il messaggio alla lista dei messaggi
        messages.append(message)

        # Ottieni la risposta dall'API di OpenAI
        new_message = get_response(messages)

    
        response_text = new_message["content"]

        response_text = elimina_righe_backtick(response_text)
        
        if cerca_OK(response_text):
            write_file(text, text_content)
            commit_changes(repo_path, text, "No accessibility error found")
            print(text)
        else:
            code, comments = split_text_at_comment(response_text)
            write_file(text, code)
            commit_changes(repo_path, text, comments)


def cerca_OK(testo):
    linee = testo.split('\n')  # Dividi il testo in righe usando il carattere di nuova riga '\n'
    
    for linea in linee:
        if "OK" in linea:
            return True
        elif "No accessibility errors found" in linea:
            return True
    
    return False


def commit_changes(repo, file_name, commit_message):
    # Aggiungi il file all'indice di staging
    repo.git.add(file_name)
    
    # Effettua il commit
    repo.index.commit(commit_message)
    
    print(f"Changes committed with message: '{commit_message}'")


def create_new_branch(repo_path):
    # Apri il repository locale
    repo = Repo(repo_path)
    
    # Verifica che il repository non sia "bare"
    if repo.bare:
        raise Exception(f"The repository at {repo_path} is bare, it must be a working tree repository.")
    
    # Genera un nome univoco per il nuovo branch utilizzando il timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new_branch_name = f"fixed-branch-{timestamp}"
    
    # Crea un nuovo branch
    new_branch = repo.create_head(new_branch_name)

    # Traccia il nuovo branch con un ramo upstream nel repository remoto
    origin = repo.remote(name='origin')
    origin.push(new_branch_name, set_upstream=True)
    
    # Passa al nuovo branch
    repo.head.reference = new_branch
    repo.head.reset(index=True, working_tree=True)
    
    print(f"New branch '{new_branch_name}' created and checked out.")

def push_changes(repo):
    # Ottieni il riferimento al repository remoto (di solito chiamato "origin")
    origin = repo.remote(name='origin')
    
    # Push delle modifiche sul branch corrente
    origin.push()
    
    print("Changes pushed to remote repository.")


if __name__ == "__main__":
    
    # Verifica che siano stati forniti correttamente due argomenti di riga di comando
    if len(sys.argv) != 3:
        print("Utilizzo: python script.py <cartella> <estensione>")
        sys.exit(1)

    cartella = sys.argv[1]  # Il primo argomento è il percorso della cartella
    estensione = sys.argv[2]  # Il secondo argomento è l'estensione dei file

    repo = Repo(cartella)
    
    
    # Crea il nuovo branch
    create_new_branch(cartella)

    
    fix_file(cartella, estensione, repo)
    if "html" in estensione:
        fix_file(cartella, "css", repo)


    push_changes(repo)
    


