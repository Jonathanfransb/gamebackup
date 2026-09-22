import sys
from datetime import datetime
import argparse
import os
import re
import json
import contextlib
from rclone_python import rclone

def dumpjson(gameslist, gamespathslist):
    return json.dumps({"games": gameslist, "savespaths": gamespathslist}, indent=4)

def get_server_data():
    gamedata_server = json.loads(rclone.cat(default_data_path_server))
    games_server = gamedata_server["games"]
    gamespaths_server = gamedata_server["savespaths"]
    return games_server, gamespaths_server

def update_server_data():
    if args.sync:
        try:
            rclone.ls(default_data_path_server)
        except:
            with contextlib.redirect_stdout(open(os.devnull, 'w')):
                create_server_data(games, gamespaths)
            for index, game in enumerate(games):
                rclone.copy(f"{gamespaths[index]}", f"{savesdir}/{game}")
            sys.exit(0)
        else:
            games_server, gamespaths_server = get_server_data()
            have_changes = False
            for index, game in enumerate(games):
                if game in games_server and gamespaths[index] not in gamespaths_server:
                    gamespaths_server[games_server.index(game)] = gamespaths[index]
                    have_changes = True
                if game not in games_server:
                    games_server.append(game)
                    gamespaths_server.append(gamespaths[index])
                    have_changes = True
            if have_changes:
                print("Applying changes to server data...")
                with contextlib.redirect_stdout(open(os.devnull, 'w')):
                    create_server_data(games_server, gamespaths_server)
            return games_server, gamespaths_server

    if args.backup:
        try:
            rclone.ls(default_data_path_server)
        except:
            with contextlib.redirect_stdout(open(os.devnull, 'w')):
                create_server_data(games_server, gamespaths_server)
            for index, game in enumerate(games_to_use):
                rclone.copy(gamespaths_to_use[index], f"{savesdir}/{game}")
            print("Server backups updated!")
            sys.exit(0)
        else:
            have_changes = False
            games_server, gamespaths_server = get_server_data()
            for index, game in enumerate(games_to_use):
                if game in games_server and gamespaths[index] not in gamespaths_server:
                    gamespaths_server[games_server.index(game)] = gamespaths[index]
                if game not in games_server:
                    games_server.append(game)
                    gamespaths_server.append(gamespaths_to_use[index])
                    have_changes = True
                if have_changes:
                    with contextlib.redirect_stdout(open(os.devnull, 'w')):
                        create_server_data(games_server, gamespaths_server)
            return games_server, gamespaths_server

    if args.download:
        try:
            rclone.ls(default_data_path_server)
        except:
            print("gamedata.json not found on server. Consider creating one using --backup or --sync")
        else:
            have_changes = False
            games_server, gamespaths_server = get_server_data()
            for index, game in enumerate(games_to_use):
                if game in games_server and gamespaths[index] not in gamespaths_server:
                    gamespaths_server[games_server.index(game)] = gamespaths[index]    
                    have_changes = True           
                else:
                    pass
                if have_changes:
                    with contextlib.redirect_stdout(open(os.devnull, 'w')):
                        create_server_data(games_server, gamespaths_server)
            return games_server, gamespaths_server 




def create_server_data(gamestodump, gamespathstodump):
    try: 
        rclone.ls(savesdir, args=["--stat"])
    except:
        rclone.mkdir(savesdir)

    newfile = dumpjson(gamestodump, gamespathstodump)
    with open(gamedata_server_name, "w") as f:
        f.write(newfile)
    rclone.move(gamedata_server_name, remote_path)

# Definição de argumentos para o CLI
parser = argparse.ArgumentParser(
	prog='gamebackup',
	description='Create or download a backup of game using ssh/sftp server.',
	epilog='')
parser.add_argument('-l', '--list', action="store_true")
parser.add_argument('--remove', action="store_true" )
#parser.add_argument('--remove-from-server', action="store_true" )
parser.add_argument('-a', '--add', action="store_true")
parser.add_argument('--download', action="store_true")
parser.add_argument('--backup', action="store_true")
parser.add_argument('--sync', action="store_true", help="Used for syncronizing server backups")
parser.add_argument('--game', type=str, help="Used for selecting the game")
parser.add_argument('--gamepath', type=str, help="Used for choosing a custom path for the game")
args = parser.parse_args()

# Definição de variaveis

games = []
gamespaths = []

linux = False
windows = False

remote_path = "gamebackup:gamebackup"
savesdir = f"{remote_path}/Saves" 

if not rclone.is_installed():
    print("rclone is not installed.")
    sys.exit(1)

if not rclone.check_remote_existing("gamebackup"):
    print("The remote gamebackup doesn't exist. Create one with rclone.")
    sys.exit(1)

home = os.path.expanduser("~")

# Verificações de SO e do arquivo de dados 
if sys.platform == "linux":
    linux = True
    gamedata_server_name = "gamedata_linux.json"
    default_data_path = f"{home}/.config/gamebackup"
    default_data_path_server = f"{remote_path}/{gamedata_server_name}"
    gamedata_file = f"{default_data_path}/gamedata.json"
    os.makedirs(default_data_path, exist_ok=True)
elif sys.platform == "win32":
    windows = True
    gamedata_server_name = "gamedata_windows.json"
    default_data_path = f"{home}\\AppData\\Local\\gamebackup"
    default_data_path_server = f"{remote_path}/{gamedata_server_name}"
    gamedata_file = f"{default_data_path}\\gamedata.json"
    os.makedirs(default_data_path, exist_ok=True)
else:
    print("System not supported")
    sys.exit(1)

if not os.path.exists(gamedata_file) and not args.add:
    print("The file containing the games data doesn't exists locally.")
    try: 
        rclone.ls(default_data_path_server, args=["--stat"])
    except:
        sys.exit(1)
    else:
        print("Found a game data on server. Copying...")
        gamedata_server_content = rclone.cat(default_data_path_server)
        gamedata = json.loads(gamedata_server_content)
        for path in gamedata["savespaths"]:
            if home not in path:
                if windows:
                    gamepath = re.sub(r"C:\\Users\\[a-zA-Z0-9]+", lambda m: home, path)
                    gamespaths.append(gamepath)
                if linux:
                    gamepath = re.sub(r"/home/[a-zA-Z0-9]+", home, path)
                    gamespaths.append(gamepath)
            elif home in path:
               gamespaths.append(path)
               
        games = gamedata["games"]
        newfile = dumpjson(games, gamespaths)
        print(newfile)
        with open(gamedata_file, "w") as f:
            f.write(newfile)

elif os.path.exists(gamedata_file):
    with open(gamedata_file) as f:
        gamedata = json.loads(f.read())

    games = gamedata["games"]
    gamespaths = gamedata["savespaths"]


# Função dos argumentos

if (args.backup or args.download or args.remove or args.add) and not args.game:
        print('Variable game is empty. Select one using --game')
        sys.exit(1)


if args.remove and args.add:
    print("Can't use --add and --remove simultaneously")
    sys.exit(1)

if (args.backup or args.sync or args.download or args.list ) and args.add:
    print("Can't use --add with other arguments simultaneously")
    sys.exit(1)

if args.gamepath and (args.backup or args.download):
    print("Can't use a custom gamepath.")
    sys.exit(1)

if args.list:
    print("The following games are available:")
    for game in games: 
        print(game)
    sys.exit(0)
if args.game:
    # Cria uma variavel que será usada para verificar quantas vezes a pesquisa retornou resultados
    timesfound = 0
    # Cria uma lista que guarda o indice da pesquisa
    games_to_use = []
    gamespaths_to_use = []
    for i, v in enumerate(games):
        if re.search(args.game, v, flags=re.I):
            games_to_use.append(v)
            gamespaths_to_use.append(gamespaths[i])

if args.remove:
    for index, game_to_use in enumerate(games_to_use):
        games.remove(game_to_use)
        gamespaths.remove(gamespaths_to_use[index])
    newfile = dumpjson(games, gamespaths)
    with open(gamedata_file, 'w') as f:
        f.write(newfile)

if args.gamepath:
    gamepath = os.path.abspath(args.gamepath)

if args.add:
    if not args.gamepath:
        print("gamepath is not defined. Use --gamepath.")
        sys.exit(1)
    for i in games:
        gamesearch = re.search(f"^({args.game})$", i, flags=re.I)
        if gamesearch:
            print("Game already exist.")
            print(f"(y/N) Do you want to overwrite with:\ngamepath: {gamepath} game: {args.game} ")
            option = input().strip().lower()
            match option:
                case 'y' | 'yes':
                    for i, v in enumerate(games):
                        if v == args.game:
                            gamespaths[i] = gamepath
                    newfile = dumpjson(games, gamespaths)
                    with open(gamedata_file, "w") as f:
                        f.write(newfile)
                    sys.exit(0)
                case 'n' | 'no' | '':
                    sys.exit(0)

    games.append(args.game)
    gamespaths.append(gamepath)
    
    newfile = dumpjson(games, gamespaths)

    with open(gamedata_file, "w") as f:
        f.write(newfile)


if args.backup:
    update_server_data()
    for index, game in enumerate(games_to_use):
        rclone.sync(gamespaths_to_use[index], f'{savesdir}/{game}', args=['--create-empty-src-dirs'])
    
if args.download:
    update_server_data()
    for index, game in enumerate(games_to_use):
        if len(rclone.ls(f"{savesdir}/{game}")) == 1 and not rclone.ls(f"{savesdir}/{game}")[0]["IsDir"]:
            if windows:
                gamepath_list = gamespaths_to_use[index].split("\\")[:-1]
                gamepath = "\\".join(gamepath_list)
            if linux:
                gamepath_list = gamespaths_to_use[index].split("/")[:-1]
                gamepath = "/".join(gamepath_list)
            rclone.copy(f'{savesdir}/{game}', gamepath, args=['--create-empty-src-dirs'])
        else:
            rclone.copy(f'{savesdir}/{game}', gamespaths_to_use[index], args=['--create-empty-src-dirs'])
            
if args.sync:
    if args.backup or args.download or args.add or args.remove or args.game or args.gamepath:
        print("Error") #TODO Mensagem de erro
        sys.exit(1)

    games_server, gamespaths_server = update_server_data()

    file_dates = []
    file_dates_server = []
    times = []


    time_unix = []

    for save in games:
        gamepath = gamespaths[games.index(save)]
        if os.path.exists(gamepath):
            if os.path.isfile(gamepath):
                file_dates.append(int(os.stat(gamepath).st_mtime))
            else:
                for path, dirnames, files in os.walk(gamepath):
                    for file in files:
                        times.append(int(os.stat(f"{path}/{file}").st_mtime))
                file_dates.append(max(times))
                times.clear()

        try:
           server_files = rclone.ls(f"{savesdir}/{save}", args=["-R"])
        except:
           pass

        for index, file in enumerate(server_files):
           if not server_files[index]["IsDir"]:
               dt = datetime.fromisoformat(server_files[index]["ModTime"])
               time_unix.append(int(dt.timestamp()))
        try:
           file_dates_server.append(max(time_unix))
        except:
           pass
        time_unix.clear()

    for index, date in enumerate(file_dates):
        game = games[index]

        if file_dates != []:
            server_date = file_dates_server[games_server.index(game)]
            if date > server_date:
                print(f"O jogo {game} possui um save local mais atualizado. Fazendo backup...")
                rclone.sync(f'{gamespaths[games.index(game)]}', f'{savesdir}/{game}', args=['--create-empty-src-dirs'])
            elif date == server_date:
                print(f"O jogo {game} possui um save local igual ao backup. Nada a fazer.")
        else:
            print(f"O jogo {game} não existe save local. Baixando backup.")
            if len(rclone.ls(f"{savesdir}/{game}")) == 1:
                if windows:
                    gamepath_list = gamespaths_server[index].split("\\")[:-1]
                    gamepath = "\\".join(gamepath_list)
                if linux:
                    gamepath_list = gamespaths_server[index].split("/")[:-1]
                    gamepath = "/".join(gamepath_list)
            rclone.sync(f'{savesdir}/{game}', f'{gamepath}')
