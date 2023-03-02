import requests
import discord
import time
import pytz
from datetime import datetime
import asyncio
from discord_slash import SlashCommand, ComponentContext
from discord_slash.utils.manage_components import create_actionrow, create_button, wait_for_component
from discord_slash.model import ButtonStyle
from algosdk import mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod
from dotenv import load_dotenv
import random
load_dotenv()

graphql = 'INSERT DGRAPH URL ENDPOINT HERE'
dg_auth = 'INSERT DGRAPH AUTHENTICATION TOKEN KEY HERE'
clawback_address = "INSERT CLAWBACK WALLET ADDRESS HERE"
sender_mnemonic = 'INSERT 25-WORD MNEMONIC SEEDPHRASE HERE'
sender_key = mnemonic.to_private_key(sender_mnemonic)

project_name = "INSERT YOUR PROJECT NAME HERE"
main_token_id = []
main_token_name = 'INSERT MAIN TOKEN NAME HERE'

algod_address = "https://mainnet-algorand.api.purestake.io/ps2"
alog_token = 'INSERT ALGOD TOKEN KEY HERE'
headers = {"X-API-Key": alog_token}
algod_client = algod.AlgodClient(alog_token, algod_address, headers)
base_url = "https://mainnet-idx.algonode.cloud/v2"
headersDG = {"DG-Auth": dg_auth}

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
slash = SlashCommand(client, sync_commands=True)
guild = client.get_guild("INSERT YOUR DISCORD SERVER GUILD ID HERE")

user_last_played = {}

embedAdminOnly = discord.Embed(
                title="⛔ WOOPS! ⛔",
                description=f"This command is reserved for admins only!",
                color=0xFF1C0A,
            )

embedCD = discord.Embed(
            title=f"Damn! That's faster than block time chill!",
            description=f"Give it a second and try again...",
            color=0xFF1C0A,
            )

embedErr = discord.Embed(
                title=f"GET ${main_token_name}",
                url="https://vestige.fi/asset/main_token_name",
                description=f"You do not own that much ${main_token_name} 😔",
                color=0xFF1C0A,
            )

embedNoOpt = discord.Embed(
                title=f"You Are Not Opted Into ${main_token_name}!",
                description=f"[Click Here To Opt In...](https://www.randgallery.com/algo-collection/?address={main_token_id})",
                color=0xFF1C0A,
            )

embedWrongChannel = discord.Embed(
            title=f"Gaming is restricted to gaming channels only",
            description=f"Please head over to that section to play! 🤑",
            color=0xFF1C0A
        )
        
async def add_games(address, won, lost, amountwon, amountlost):
    addgame = """
    mutation addGame($address: String!, $won: Int!, $lost: Int!, $amountwon: Int!, $amountlost: Int!) {
      updateDiscordWallets(input: {filter: {address: {eq: $address}}, set: {won: $won, , lost: $lost, amountwon: $amountwon, amountlost: $amountlost}}) {
            numUids
        }
    }
    """
    variables = {'address': address, 'won': won, 'lost': lost, 'amountwon': amountwon, 'amountlost': amountlost}
    request = requests.post(graphql, json={'query': addgame, 'variables': variables}, headers=headersDG)
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception("Update Query failed to run by returning code of {}. {}".format(request.status_code, addgame))

async def add_drip(address, current_time, new_main_token_name):
    add_drip = """
    mutation addDrip($address: String!, $lastdrip: DateTime!, $new_main_token_name: Int!) {
      updateDiscordWallets(input: {filter: {address: {eq: $address}}, set: {lastdrip: $lastdrip, drip_main_token_name: $new_main_token_name}}) {
            numUids
        }
    }
    """
    variables = {'address': address, 'lastdrip': current_time, 'new_main_token_name': new_main_token_name}
    request = requests.post(graphql, json={'query': add_drip, 'variables': variables}, headers=headersDG)
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception("Update Query failed to run by returning code of {}. {}".format(request.status_code, add_drip))
    

async def get_all_wallets():

    getallwallets = """
    query queryDiscordWallets {
        queryDiscordWallets {
            address
            name
            userid
        }
    }
    """
    request = requests.post(graphql, json={'query': getallwallets}, headers=headersDG)
    if request.status_code == 200:
        result = request.json()
        if result['data']['queryDiscordWallets'] == []:
            wallets = []
        else:
            wallets = result['data']['queryDiscordWallets']
            
        return wallets


async def send_assets(sender, sender_address, receiver_address, token, token_name, amount):
    decimals = algod_client.asset_info(token).get("params").get("decimals")
    note = "INSERT CUSTOM SEND NOTE HERE"

    params = algod_client.suggested_params()
    txn = transaction.AssetTransferTxn(
        clawback_address,
        params,
        receiver_address,
        amt=amount * (10 ** decimals),
        index=token,
        revocation_target=sender_address,
        note=note
    )

    signed_txn = txn.sign(sender_key)
    tx_id = algod_client.send_transaction(signed_txn)

    return tx_id
    

async def deathmatch_clawback(user_address):
    decimals = algod_client.asset_info(main_token_id).get("params").get("decimals")
    note = f"Fallen Order - Death Match! You successfully sign up for 50 ${main_token_name}. Good Luck!"

    params = algod_client.suggested_params()

    txn = transaction.AssetTransferTxn(
        clawback_address,
        params,
        clawback_address,
        amt=50 * (10 ** decimals),
        index=main_token_id,
        revocation_target=user_address,
        note=note.encode()
    )

    signed_txn = txn.sign(sender_key)

    tx_id = algod_client.send_transaction(signed_txn)

    return tx_id   

async def clawback_main_token(user_address, amount, type):
    decimals = algod_client.asset_info(main_token_id).get("params").get("decimals")
    noteLoss = "INSERT NOTE FOR LOSS HERE"
    noteTie = "INSERT NOTE FOR TIE HERE"
    noteWin = "INSERT NOTE FOR WIN HERE"

    params = algod_client.suggested_params()

    if type == "loss":
        txn = transaction.AssetTransferTxn(
            clawback_address,
            params,
            clawback_address,
            amt=amount * (10 ** decimals),
            index=main_token_id,
            revocation_target=user_address,
            note=noteLoss.encode()
        )
    elif type == "tie":
        txn = transaction.AssetTransferTxn(
            clawback_address,
            params,
            user_address,
            amt=amount*2 * (10 ** decimals),
            index=main_token_id,
            revocation_target=clawback_address,
            note=noteTie.encode()
        )
    elif type == "win":
        txn = transaction.AssetTransferTxn(
            clawback_address,
            params,
            user_address,
            amt=amount * (10 ** decimals),
            index=main_token_id,
            revocation_target=clawback_address,
            note=noteWin.encode()
        )

    signed_txn = txn.sign(sender_key)

    tx_id = algod_client.send_transaction(signed_txn)

    return tx_id


@slash.slash(name="leaderboard", description="Check Rankings for House Of Hermes!", options=[
                {
                    "name": "count",
                    "description": "Rankings To Display",
                    "type": 4,
                    "required": True
                },
                {
                    "name": "sortby",
                    "description": "Sorting Method",
                    "type": 3,
                    "required": True,
                    "choices": [
                        {
                            "name": "Won",
                            "value": "won"
                        },
                        {
                            "name": "Lost",
                            "value": "lost"
                        },
                        {
                            "name": f"{main_token_name} Won",
                            "value": "amountwon"
                        },
                        {
                            "name": f"{main_token_name} Lost",
                            "value": "amountlost"
                        }
                    ]
                }
            ])

async def get_games(ctx, count, sortby):

    getgames = f"""
    query getGames {{
        queryDiscordWallets(order: {{desc: {sortby}}}) {{
            address
            name
            amountlost
            amountwon
            id
            userid
            lost
            won
        }}
    }}
    """
    request = requests.post(graphql, json={'query': getgames}, headers=headersDG)
    result = request.json()

    embedLeaderboard = discord.Embed(title='Leaderboard - House Of Hermes', description='Those who have dared to take on Hermes:', color=0xFFFB0A)

    counter = 0
    limit = count

    for field in result['data']['queryDiscordWallets']:
        if counter == limit:
            break

        if field['won'] == 0 or field['lost'] == 0 or field['amountwon'] == 0 or field['amountlost'] == 0:
            continue
        else:
            embedLeaderboard.add_field(name=field['name'], value=f"Total Games - {field['won'] + field['lost']}\nW | L - {field['won']} | {field['lost']}\nW | L ${main_token_name} - {field['amountwon']} | {field['amountlost']}\n P | L - {round(field['amountwon']/field['amountlost'],3)}", inline=False)
            
        counter += 1

    await ctx.send(embed=embedLeaderboard)

async def get_wallet(userid):

    getwallet = f"""
    query queryDiscordWallets {{
        queryDiscordWallets(filter: {{userid: {{eq: "{userid}"}}}}) {{
            address
            name
            lost
            won
            amountwon
            amountlost
            lastdrip
            drip_main_token_name
        }}
    }}
    """
    variables = {'userid': userid}
    request = requests.post(graphql, json={'query': getwallet, 'variables': variables}, headers=headersDG)
    if request.status_code == 200:
        result = request.json()
        if result['data']['queryDiscordWallets'] == []:
            wallet = ''
            name = ''
            won = 0
            lost = 0
            amountwon = 0
            amountlost = 0
            lastdrip = ''
            drip_main_token_name = 0
        else:
            wallet = result['data']['queryDiscordWallets'][0]['address']
            name = result['data']['queryDiscordWallets'][0]['name']
            won = result['data']['queryDiscordWallets'][0]['won']
            lost = result['data']['queryDiscordWallets'][0]['lost']
            amountwon = result['data']['queryDiscordWallets'][0]['amountwon']
            amountlost = result['data']['queryDiscordWallets'][0]['amountlost']
            lastdrip = result['data']['queryDiscordWallets'][0]['lastdrip']
            drip_main_token_name = result['data']['queryDiscordWallets'][0]['drip_main_token_name']

        return wallet, name, won, lost, amountwon, amountlost, lastdrip, drip_main_token_name

async def get_all_wallets():

    getallwallets = f"""
    query queryDiscordWallets {{
        queryDiscordWallets {{
            address
            name
            userid
        }}
    }}
    """
    request = requests.post(graphql, json={'query': getallwallets}, headers=headersDG)
    if request.status_code == 200:
        result = request.json()
        if result['data']['queryDiscordWallets'] == []:
            wallets = []
        else:
            wallets = result['data']['queryDiscordWallets']
            
        return wallets

async def get_balance(address):
    endpoint = f"{base_url}/accounts/{address}"
    response = requests.get(endpoint, headers=headers)

    if response.status_code != 200:
        raise Exception("API request failed")
        
    account_data = response.json()["account"]
    
    for asset in account_data["assets"]:
        if asset["asset-id"] == main_token_id:
            balance = asset["amount"]
            break
    else:
        balance = -1

    return balance
   

@slash.slash(name="drip", description=f"Drips Out 1-5 ${main_token_name} Every 6 Hours!")

async def drip_claim(ctx):
    await ctx.defer()
    userid = str(ctx.author.id)

    wallet, name, won, lost, amountwon, amountlost, lastdrip, drip_main_token_name = await get_wallet(userid)
    balance = await get_balance(wallet, main_token_name)

    if balance == -1:
        await ctx.send(embed=embedNoOpt)
        return
    if wallet == '':
        await ctx.send("User not registered..")
        return
    else:
        utc = pytz.timezone('UTC')

        lastdrip_datetime = datetime.strptime(lastdrip, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=utc)
        now = datetime.now(utc)
        time_diff = now - lastdrip_datetime
        total_seconds = time_diff.total_seconds()

        if total_seconds < 6 * 60 * 60:
            next_claim = ((60*60*6) - total_seconds)
            timer = ((datetime.fromtimestamp(next_claim)).strftime('%HH %MM %SS')).lstrip('0')
            if timer.startswith("H "):
                dt = timer[2:]
            else:
                dt = timer
            embedNoDrip = discord.Embed(
                title=f"You have already made a drip claim less than 6 hours ago!",
                description=f"Please come back when your timer resets...",
                color=0xFF1C0A,
                )
            embedNoDrip.set_footer(text=f"Next Claim In {dt} ⏱️")
            await ctx.send(embed=embedNoDrip)
        else:
            main_token_name = [1, 2, 3, 4, 5]
            random_main_token_name = random.choice(main_token_name)
            new_main_token_name = int(drip_main_token_name + random_main_token_name)
            embedDrip = discord.Embed(
                title=f"💸 ${main_token_name} DRIP! 💸",
                footer=f"Next Claim In 6 Hours ⏱️",
                color=0x28FF0A,
                )
            embedDrip.set_thumbnail(url="https://s3.amazonaws.com/algorand-wallet-mainnet-thumbnails/prism-images/media/assets-logo-png/2022/10/11/a26da3af714a40e8bad2b29a6dfc4655.png--resize--w__200--q__70.webp")
            current_time = (datetime.now()).strftime('%Y-%m-%dT%H:%M:%SZ')
            txnid = await send_assets(project_name, clawback_address, wallet, main_token_name, f"{main_token_name}", random_main_token_name)
            embedDrip.add_field(name=f"Dripped out {random_main_token_name} ${main_token_name} to <@{ctx.author.id}>!", value=f"[Txn Link](https://algoexplorer.io/tx/{txnid})", inline=True)
            embedDrip.set_footer(text=f"Enjoy the games! 💛")
            await ctx.send(embed=embedDrip)

            await add_drip(wallet, current_time, new_main_token_name)

        return



@slash.slash(name="send", description=f"Send {main_token_name} to other users", options=[
                {
                    "name": "user",
                    "description": "Receiving User",
                    "type": 6,
                    "required": True
                },
                {
                    "name": "amount",
                    "description": "Amount To Send",
                    "type": 4,
                    "required": True
                }
            ])

async def send(ctx, user, amount):
    sender = ctx.author.id
    receiver = user.id
    sender_name = ctx.author.name

    wallet1, name1, won1, lost1, amountwon1, amountlost1, lastdrip1, drip_main_token_name1 = await get_wallet(sender)
    wallet2, name2, won2, lost2, amountwon2, amountlost2, lastdrip1, drip_main_token_name1 = await get_wallet(receiver)

    if wallet1 == '' or wallet2 == '':
        await ctx.send("User not registered..")
        return
    else:
        sender_balance = await get_balance(wallet1, main_token_id) 
        receiver_balance = await get_balance(wallet2, main_token_id)
        
        if sender_balance == 0:
            await ctx.send(embed=embedErr)
            return
        elif sender_balance < amount:
            await ctx.send(embed=embedErr)
            return
        else:
            txnid = await send_assets(sender_name, wallet1, wallet2, main_token_id, main_token_name, amount)
            new_sender_bal = sender_balance - amount
            new_receiver_bal = receiver_balance + amount
            embedSent = discord.Embed(
                    title=f"I have bestowed {amount} ${main_token_name} upon <@{receiver}>",
                    description=f"Sent By: <@{sender}> 💛 [Txn Link](https://algoexplorer.io/tx/{txnid})",
                    color=0xFFFB0A
                )
            embedSent.set_footer(text=f"{sender_name}'s New Balance: {new_sender_bal} ${main_token_name}.")
            await ctx.send(embed=embedSent)
            return


@slash.slash(name="stats", description="Check Your Personal Stats!")

async def stats(ctx):
    if ctx.channel.id != "INSERT GAME CHANNEL ID HERE TO RESTRICT ACCESS":
        await ctx.send(embed=embedWrongChannel)
        return
    else:
        wallet, name, won, lost, amountwon, amountlost, lastdrip, drip_main_token_name = await get_wallet(str(ctx.author.id))
        
        if wallet == '':
            embedNoReg = discord.Embed(
                    title="Click Here To Register!",
                    url="INSERT REGISTER WEBSITE HERE",
                    description=f"Please verify your wallet via our website to continue..",
                    color=0xFF1C0A,
                )
            await ctx.send(embed=embedNoReg)
            return
        if won == 0 or lost == 0 or amountwon == 0 or amountlost == 0:
            embedNoStats = discord.Embed(
                    title=f"You don't have enough games to produce stats..",
                    description=f"Play a couple games and try again!",
                    color=0xFF1C0A
                )
            await ctx.send(embed=embedNoStats)
            return
        else:
            balance = await get_balance(wallet, main_token_id)
            embedStats = discord.Embed(
                    title=f"Personal Stats - {name}",
                    description=f"Balance: {balance} ${main_token_name}",
                    color=0xFFFB0A
                )
            
            embedStats.add_field(name=f"Total Games: {won + lost}", value=f"Won: {won} | Lost: {lost}", inline=True)
            embedStats.add_field(name=f"Won/Lost ${main_token_name}: {amountwon} | {amountlost}", value=f"P/L: {round(amountwon/amountlost,3)}", inline=True)
            embedStats.set_footer(text=f"W/L Ratio: {round(won/lost,3)}")

            await ctx.send(embed=embedStats)
            return

# vvvvvvvvv BLACKJACK vvvvvvvvvv

suits = ['♠️', '♥️', '♣️', '♦️']
values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

def new_deck():
    deck = [(value, suit) for value in values for suit in suits]
    random.shuffle(deck)
    return deck

def calculate_hand(hand):
    total = 0
    aces = 0
    for value, suit in hand:
        if value == 'A':
            aces += 1
            total += 11
        elif value in ['K', 'Q', 'J']:
            total += 10
        else:
            total += int(value)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

game_activebj=0

@slash.slash(name="blackjack", description="Play BlackJack with Hermes!", options=[
                {
                    "name": "bet",
                    "description": "Bet Amount",
                    "type": 4,
                    "required": True,
                }
            ])
async def blackjack(ctx, bet):
    if ctx.channel.id != "INSERT GAME CHANNEL ID HERE TO RESTRICT ACCESS":
        await ctx.send(embed=embedWrongChannel)
        return
    global game_activebj
    while game_activebj >= 2:
        embedMaxBJ = discord.Embed(
            title=f"There are two active Blackjack games...",
            description=f"Please wait while current games end...",
            color=0xFF0000
        )
        await ctx.send(embed=embedMaxBJ)
        return
    else:
        user_id = ctx.author.id

        embedMax = discord.Embed(
                title=f"Your bet of {bet} is not allowed!",
                description=f"Please enter a bet amount 1-1000",
                color=0xFF0080
            )

        if user_id not in user_last_played:
            user_last_played[user_id] = time.monotonic()
        else:
            time_diff = time.monotonic() - user_last_played[user_id]
            if time_diff >= 10:
                user_last_played[user_id] = time.monotonic()
            else:
                await ctx.send(embed=embedCD)
                return
        
        wallet, name, won, lost, amountwon, amountlost, lastdrip, drip_main_token_name = await get_wallet(str(ctx.author.id))

        if wallet == '':
            await ctx.send("User is not registered..")
            return
        else:
            balance = await get_balance(wallet, main_token_name)

            if (bet <= 1000):
                if balance == 0:
                    await ctx.send(embed=embedErr)
                elif balance < bet:
                    await ctx.send(embed=embedErr)
                else:
                    game_activebj += 1
                    deck = new_deck()
                    player_hand = [deck.pop(), deck.pop()]
                    dealer_hand = [deck.pop()]

                    embedBJ = discord.Embed(title=f"🃏 Blackjack - {name}", description=f"Bet: {bet} ${main_token_name}", color=0x00ff00)
                    embedBJ.add_field(name=f"{name}'s hand - {calculate_hand(player_hand)}", value=f"{player_hand[0][0]} {player_hand[0][1]} | {player_hand[1][0]} {player_hand[1][1]}", inline=False)
                    embedBJ.add_field(name=f"Hermes' hand - {calculate_hand(dealer_hand)}", value=f"{dealer_hand[0][0]} {dealer_hand[0][1]}", inline=False)
                    message = await ctx.send(embed=embedBJ)
                    player_total = calculate_hand(player_hand)
                    await message.edit(embed=embedBJ)

                    while player_total < 21:
                        action_row = create_actionrow(
                            create_button(style=ButtonStyle.green, label="Hit", custom_id="hit"),
                            create_button(style=ButtonStyle.red, label="Stand", custom_id="stand"),
                            create_button(style=ButtonStyle.blurple, label="Double Down", custom_id="double_down")
                        )

                        await message.edit(components=[action_row])
                        try:
                            interaction: ComponentContext = await wait_for_component(client, components=action_row, timeout=10.0)
                            interaction_author_id = interaction.author.id

                            if interaction_author_id == ctx.author.id:
                                await interaction.defer(edit_origin=True)
                                action = interaction.custom_id
                                if action == "hit":
                                    player_hand.append(deck.pop())
                                    player_total = calculate_hand(player_hand)
                                    embedBJ.set_field_at(0, name=f"{name}'s hand - {player_total}", value=' | '.join([f'{v}{s}' for v, s in player_hand]))
                                    embedBJ.set_field_at(1, name=f"Hermes' hand - {calculate_hand(dealer_hand)}", value=f"{dealer_hand[0][0]} {dealer_hand[0][1]}")
                                    await message.edit(embed=embedBJ)
                                    if player_total > 21:
                                        break
                                elif action == "double_down":
                                    if bet == 0:
                                        bet = bet
                                    else:
                                        balance = await get_balance(wallet, main_token_name)
                                        if balance < bet*2:
                                            await ctx.send(embed=embedErr)
                                            break
                                        else:
                                            bet *= 2
                                    player_hand.append(deck.pop())
                                    player_total = calculate_hand(player_hand)
                                    if bet == 0:
                                        embedBJ.description = f"Bet: {bet} + {bet} ${main_token_name}"
                                    else:
                                        embedBJ.description = f"Bet: {bet/2} + {bet/2} ${main_token_name}"
                                    embedBJ.set_field_at(0, name=f"{name}'s hand - {player_total}", value=' | '.join([f'{v}{s}' for v, s in player_hand]))
                                    embedBJ.set_field_at(1, name=f"Hermes' hand - {calculate_hand(dealer_hand)}", value=f"{dealer_hand[0][0]} {dealer_hand[0][1]}")
                                    await message.edit(embed=embedBJ)
                                    break
                                else:
                                    break
                            else:
                                embedWrongGame = discord.Embed(
                                    title=f"This is not your game!",
                                    description=f"{ctx.author.name} is currently playing..",
                                    color=0xFF0000
                                )
                                await interaction.reply(embed=embedWrongGame, hidden=True)
                        except asyncio.TimeoutError:
                            embedTimeout = discord.Embed(
                                    title=f"Woops! You took too long to respond...",
                                    description=f"Ending {ctx.author.name}'s game..",
                                    color=0xFF0000
                                )
                            await message.edit(embed=embedTimeout, components=[])
                            await asyncio.sleep(6)
                            await message.delete()
                            game_activebj -= 1
                            return
                    
                    
                    # Dealer's turn
                    dealer_total = calculate_hand(dealer_hand)
                    if player_total == 21:
                            newwon = won + 1
                            newlost = lost
                            newamountwon = amountwon + bet
                            newamountlost = amountlost
                            newbalance = balance + bet
                            embedBJ.set_footer(text=f"BLACKJACK!! {name} WON! 🔥 | New Balance: {newbalance} ${main_token_name}")
                            embedBJ.color = 0x28FF0A
                            await message.edit(embed=embedBJ, components=[])
                            await clawback_main_token(wallet, bet, "win")

                    elif len(player_hand) == 5 and player_total < 21:
                            newwon = won + 1
                            newlost = lost
                            newamountwon = amountwon + bet
                            newamountlost = amountlost
                            newbalance = balance + bet
                            embedBJ.set_footer(text=f"FIVE CARD AUTO-WIN by {name}! 🔥 | New Balance: {newbalance} ${main_token_name}")
                            embedBJ.color = 0x28FF0A
                            await message.edit(embed=embedBJ, components=[])
                            await clawback_main_token(wallet, bet, "win")
                    
                    else:                    
                        # Determine the winner
                        if player_total > 21:
                            newbalance = balance - bet
                            newwon = won
                            newlost = lost + 1
                            newamountwon = amountwon
                            newamountlost = amountlost + bet
                            embedBJ.set_footer(text=f"{name} busted! Hermes wins! 😔 | New Balance: {newbalance} ${main_token_name}")
                            embedBJ.color = 0xFF1C0A
                            await message.edit(embed=embedBJ, components=[])
                            await clawback_main_token(wallet, bet, "loss")
                        
                        else:
                            while dealer_total < 17:
                                dealer_hand.append(deck.pop())
                                dealer_total = calculate_hand(dealer_hand)

                            # Add dealer's hand to the final message
                            dealer_hand_str = ' | '.join([f'{v}{s}' for v, s in dealer_hand])
                            embedBJ.set_field_at(0, name=f"{name}'s hand - {calculate_hand(player_hand)}", value=' '.join([f'{v}{s}' for v, s in player_hand]))
                            embedBJ.set_field_at(1, name=f"Hermes' hand - {calculate_hand(dealer_hand)}", value=dealer_hand_str)
                            await message.edit(embed=embedBJ)

                            if dealer_total > 21:
                                newbalance = balance + bet
                                newwon = won + 1
                                newlost = lost
                                newamountwon = amountwon + bet
                                newamountlost = amountlost
                                embedBJ.set_footer(text=f"Hermes' busted! {name} wins! 😎 | New Balance: {newbalance} ${main_token_name}")
                                embedBJ.color = 0x28FF0A
                                await message.edit(embed=embedBJ)
                                await clawback_main_token(wallet, bet, "win")
                            elif player_total > dealer_total:
                                newwon = won + 1
                                newlost = lost
                                newamountwon = amountwon + bet
                                newamountlost = amountlost
                                newbalance = balance + bet
                                embedBJ.set_footer(text=f"{name} wins! 🔥 | New Balance: {newbalance} ${main_token_name}")
                                embedBJ.color = 0x28FF0A
                                await message.edit(embed=embedBJ)
                                await clawback_main_token(wallet, bet, "win")
                            elif dealer_total > player_total:
                                newbalance = balance - bet
                                newwon = won
                                newlost = lost + 1
                                newamountwon = amountwon
                                newamountlost = amountlost + bet
                                embedBJ.set_footer(text=f"Hermes wins! 😈 | New Balance: {newbalance} ${main_token_name}")
                                embedBJ.color = 0xFF1C0A
                                await message.edit(embed=embedBJ)
                                await clawback_main_token(wallet, bet, "loss")
                            else:
                                newbalance = balance
                                newwon = won
                                newlost = lost
                                newamountwon = amountwon
                                newamountlost = amountlost
                                embedBJ.set_footer(text=f"It's a push! 🎯 | New Balance: {newbalance} ${main_token_name}")
                                embedBJ.color = 0xFFFB0A
                                await message.edit(embed=embedBJ)
                        
                    await message.edit(components=[])
                    game_activebj -= 1
                    await add_games(wallet, newwon, newlost, newamountwon, newamountlost)
                    return

            else:
                await ctx.send(embed=embedMax)
                return
            
# ^^^^^^^^^ BLACKJACK ^^^^^^^^^^

# vvvvvvvvv ROCK PAPER SCISSORS vvvvvvvvvv

@slash.slash(name="rps", description="Rock, Paper, Scissors!", options=[
                {
                    "name": "rps",
                    "description": "Rock/Paper/Scissors",
                    "type": 3,
                    "required": True,
                    "choices": [
                        {
                            "name": "Rock",
                            "value": "Rock"
                        },
                        {
                            "name": "Paper",
                            "value": "Paper"
                        },
                        {
                            "name": "Scissors",
                            "value": "Scissors"
                        }
                    ]
                },
                {
                    "name": "bet",
                    "description": "Bet Amount",
                    "type": 4,
                    "required": True,
                }
            ])

async def rps(ctx, rps, bet):
    if ctx.channel.id != "INSERT GAME CHANNEL ID HERE TO RESTRICT ACCESS":
        await ctx.send(embed=embedWrongChannel)
        return
    else:
        user_id = ctx.author.id

        embedMax = discord.Embed(
                title=f"Your bet of {bet} is not allowed!",
                description=f"Please enter a bet amount 1-1000",
                color=0xFF0080
            )

        if user_id not in user_last_played:
            user_last_played[user_id] = time.monotonic()
        else:
            time_diff = time.monotonic() - user_last_played[user_id]
            if time_diff >= 10:
                user_last_played[user_id] = time.monotonic()
            else:
                await ctx.send(embed=embedCD)
                return

        rpsBot = ["Rock", "Paper", "Scissors"]
        randomChoice = random.choice(rpsBot)
        wallet, name, won, lost, amountwon, amountlost, lastdrip, drip_main_token_name = await get_wallet(str(ctx.author.id))

        if wallet == '':
            await ctx.send("User is not registered..")
            return
        else:
            balance = await get_balance(wallet, main_token_id)

            if (bet <= 1000):

                embedLoss = discord.Embed(
                    title=f"<@{ctx.author.id}>'s {rps} got wrecked...what a LOSS 😔",
                    description=f"Bet: {bet} ${main_token_name}",
                    color=0xFF1C0A
                )

                embedTie = discord.Embed(
                    title=f"<@{ctx.author.id}> & Hermes both play {rps}...it's a TIE! 🎯",
                    description=f"Bet: {bet} ${main_token_name}",
                    color=0xFFFB0A
                )

                embedWin = discord.Embed(
                    title=f"<@{ctx.author.id}>'s {rps} destroys Hermes' {randomChoice}...a WIN by fate! 🔥",
                    description=f"Bet: {bet} ${main_token_name}",
                    color=0x28FF0A
                )

                if balance == 0:
                    await ctx.send(embed=embedErr)
                elif balance < bet:
                    await ctx.send(embed=embedErr)
                else:
                    if rps == randomChoice:
                        newwon = won
                        newamountwon = amountwon
                        newlost = lost
                        newamountlost = amountlost
                        embedTie.add_field(name=f"{name} - {rps}", value=f'Hermes - {randomChoice}', inline=True)
                        embedTie.add_field(name="New Balance: ", value=f"{balance} ${main_token_name}", inline=True)
                        embedFinal=embedTie
                    elif (randomChoice == "Rock" and rps == "Scissors") or (randomChoice == "Scissors" and rps == "Paper") or (randomChoice == "Paper" and rps == "Rock"):
                        new_balance = balance - bet
                        newwon = won
                        newamountwon = amountwon
                        newlost = lost + 1
                        newamountlost = amountlost + bet
                        embedLoss.add_field(name=f"Hermes - {randomChoice}", value=f'{name} - {rps}', inline=True)
                        embedLoss.add_field(name="New Balance: ", value=f"{new_balance} ${main_token_name}", inline=True)
                        embedFinal=embedLoss
                        await clawback_main_token(wallet, bet, "loss")
                    elif (randomChoice == "Rock" and rps == "Paper") or (randomChoice == "Scissors" and rps == "Rock") or (randomChoice == "Paper" and rps == "Scissors"):
                        new_balance = balance + bet
                        newwon = won + 1
                        newamountwon = amountwon + bet
                        newlost = lost
                        newamountlost = amountlost
                        embedWin.add_field(name=f"{name} - {rps}", value=f'Hermes - {randomChoice}', inline=True)
                        embedWin.add_field(name="New Balance: ", value=f"{new_balance} ${main_token_name}", inline=True)
                        embedFinal=embedWin
                        await clawback_main_token(wallet, bet, "win")
                    
                    await add_games(wallet, newwon, newlost, newamountwon, newamountlost)
                    await ctx.send(embed=embedFinal)
                    return

            else:
                await ctx.send(embed=embedMax)
                return
    return

# ^^^^^^^^^ ROCK PAPER SCISSORS ^^^^^^^^^^

# vvvvvvvvv DICE vvvvvvvvvv

@slash.slash(name="dice", description="Play Dice With Hermes!", options=[
                {
                    "name": "bet",
                    "description": "Bet Amount",
                    "type": 4,
                    "required": True
                }
            ])

async def roll(ctx, bet):
    if ctx.channel.id != "INSERT GAME CHANNEL ID HERE TO RESTRICT ACCESS":
        await ctx.send(embed=embedWrongChannel)
        return
    else:
        user_id = ctx.author.id

        if user_id not in user_last_played:
            user_last_played[user_id] = time.monotonic()
        else:
            time_diff = time.monotonic() - user_last_played[user_id]
            if time_diff >= 10:
                user_last_played[user_id] = time.monotonic()
            else:
                await ctx.send(embed=embedCD)
                return

        user_rand_num = random.randint(1, 100)
        rand_num = random.randint(1, 100)
        wallet, name, won, lost, amountwon, amountlost, lastdrip, drip_main_token_name = await get_wallet(str(ctx.author.id))
        if wallet == '':
            await ctx.send("User is not registered..")
            return
        else:
            balance = await get_balance(wallet, main_token_id) 

            embedMax = discord.Embed(
                title=f"Your bet of {bet} is not allowed!",
                description=f"Please enter a bet amount 1-1000",
                color=0xFF1C0A,
            )

            if (bet <= 1000):

                embedLoss = discord.Embed(
                    title=f"<@{ctx.author.id}> rolls against Hermes...{name} lost 😔",
                    description=f"Bet: {bet} ${main_token_name}",
                    color=0xFF1C0A
                )

                embedTie = discord.Embed(
                    title=f"BULLSEYE!!! <@{ctx.author.id}> rolls against Hermes...{name} DOUBLED their bet! 🎯",
                    description=f"Bet: {bet} ${main_token_name}",
                    color=0xFFFB0A
                )

                embedWin = discord.Embed(
                    title=f"<@{ctx.author.id}> rolls against Hermes...{name} WON! 🔥",
                    description=f"Bet: {bet} ${main_token_name}",
                    color=0x28FF0A
                )

                if balance == 0:
                    await ctx.send(embed=embedErr)
                elif balance < bet:
                    await ctx.send(embed=embedErr)
                else:
                    if user_rand_num < rand_num:
                        await clawback_main_token(wallet, bet, "loss")
                        new_balance = balance - bet
                        newlost = lost+1
                        newamountlost = amountlost + bet
                        newwon = won
                        newamountwon = amountwon
                        embedLoss.add_field(name=f"Hermes - {rand_num}", value=f'{name} - {user_rand_num}', inline=True)
                        embedLoss.add_field(name="New Balance: ", value=f"{new_balance} ${main_token_name}", inline=True)
                        embedFinal=embedLoss
                    elif user_rand_num == rand_num:
                        await clawback_main_token(wallet, bet, "tie")
                        new_balance = balance + bet*2
                        newwon = won + 1
                        newamountwon = amountwon + bet
                        newlost = lost
                        newamountlost = amountlost
                        embedTie.add_field(name=f"{name} - {user_rand_num}", value=f'Hermes - {rand_num}', inline=True)
                        embedTie.add_field(name="New Balance: ", value=f"{new_balance} ${main_token_name}", inline=True)
                        embedFinal=embedTie
                    else:
                        await clawback_main_token(wallet, bet, "win")
                        new_balance = balance + bet
                        newwon = won + 1
                        newamountwon = amountwon + bet
                        newlost = lost
                        newamountlost = amountlost
                        embedWin.add_field(name=f"{name} - {user_rand_num}", value=f'Hermes - {rand_num}', inline=True)
                        embedWin.add_field(name="New Balance: ", value=f"{new_balance} ${main_token_name}", inline=True)
                        embedFinal=embedWin
                    
                    await add_games(wallet, newwon, newlost, newamountwon, newamountlost)
                    await ctx.send(embed=embedFinal)
                    return

            else:
                await ctx.send(embed=embedMax)
                return
        return

# ^^^^^^^^^ DICE ^^^^^^^^^^

#Insert Your Bot Token Here
client.run('YOUR_BOT_TOKEN')

