from spade.agent import Agent
from spade.message import Message
from spade.behaviour import CyclicBehaviour
import asyncio
import pandas as pd

class SenderAgent(Agent):
    class SendMessageBehaviour(CyclicBehaviour):
        async def run(self):
            await asyncio.sleep(5)  
            msg = Message(to="prviagent@localhost") 
            msg.set_metadata("performative", "inform")
            msg.body = input("Unesite proizvod za koji zelite znati cijenu u Dm-u: ")  

            await self.send(msg)
            print(f"Posalji poruku {msg.to} za proizvod: {msg.body}")
            self.kill()  
    class HandleResponseBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=20)  
            if msg:
                print(f"Primljen odgovor za proizvod: {msg.body}")

    async def setup(self):
        send_behaviour = self.SendMessageBehaviour()
        self.add_behaviour(send_behaviour)
        self.add_behaviour(self.HandleResponseBehaviour())

class DmAgent(Agent):
    class RespondToInquiry(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)  # cekaj 10 sekundi na poruku
            if msg:
                product_name = msg.body
                product_info = self.agent.product_data.get(product_name, None)
                
                reply = msg.make_reply()
                if product_info:
                    reply.body = f"Cijena proizvoda '{product_name}' u DM-u je {product_info} EUR."
                else:
                    reply.body = f"Proizvod '{product_name}' ne postoji"
                await self.send(reply)


    async def setup(self):
        self.product_data = pd.read_csv('/home/vjezbe/Downloads/dm.csv').set_index('Proizvod')['Redovna Cijena (EUR)'].to_dict()
        #print(self.product_data) #ispis svih proizvoda iz datoteke
        self.add_behaviour(self.RespondToInquiry())

class SenderAgent2(Agent):
    class SendMessageBehaviour(CyclicBehaviour):
        async def run(self):
            await asyncio.sleep(5)  #cekaj prije slanja poruke
            msg = Message(to="drugiagent@localhost")  
            msg.set_metadata("performative", "inform")
            msg.body = input("Unesite proizvod za koji zelite znati cijenu u Bipi: ")  

            await self.send(msg)
            print(f"Posalji poruku {msg.to} za proizvod: {msg.body}")
            self.kill()  
    class HandleResponseBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=20)  
            if msg:
                print(f"Primljen odgovor za proizvod: {msg.body}")

    async def setup(self):
        send_behaviour = self.SendMessageBehaviour()
        self.add_behaviour(send_behaviour)
        self.add_behaviour(self.HandleResponseBehaviour())

class BipaAgent(Agent):
    class RespondToInquiry(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)  
            if msg:
                product_name = msg.body
                product_info = self.agent.product_data.get(product_name, None)
                
                reply = msg.make_reply()
                if product_info:
                    reply.body = f"Cijena proizvoda '{product_name}' u Bipi je {product_info} EUR."
                else:
                    reply.body = f"Proizvod '{product_name}' ne postoji"
                await self.send(reply)
    async def setup(self):
        
        self.product_data = pd.read_csv('/home/vjezbe/Downloads/bipa.csv').set_index('Proizvod')['Redovna Cijena (EUR)'].to_dict()
        #print(self.product_data) #ispis svih proizvoda iz datoteke
        self.add_behaviour(self.RespondToInquiry())
 
class ComparatorAgent(Agent):
    class ComparePricesBehaviour(CyclicBehaviour):
        async def run(self):
            product_name = input("Unesite proizvod za koji zelite znati gdje je jeftiniji: ")

            msg_dm = Message(to="prviagent@localhost")  #  DmAgent
            msg_dm.set_metadata("performative", "inform")
            msg_dm.body = product_name
            await self.send(msg_dm)

            msg_bipa = Message(to="drugiagent@localhost")  #   BipaAgent
            msg_bipa.set_metadata("performative", "inform")
            msg_bipa.body = product_name
            await self.send(msg_bipa)

            responses = {}
            for _ in range(2):
                reply = await self.receive(timeout=30)
                if reply:
                    sender = reply.sender.localpart
                    responses[sender] = reply.body

            if all("Ovaj proizvod ne postoji" in response for response in responses.values()):
                print("Ovaj proizvod ne postoji u niti jednoj trgovini.")
            else:
                price_dm = extract_price(responses["prviagent"])
                price_bipa = extract_price(responses["drugiagent"])

                if price_dm != float('inf') and price_bipa != float('inf'):
                    cheaper_store = "Dm-u" if price_dm < price_bipa else "Bipi"
                    print(f"Proizvod '{product_name}' je jeftiniji u {cheaper_store}. (U Dm-u: {price_dm} EUR, a u Bipi: {price_bipa} EUR)")

                    result_msg = Message(to="listagent@localhost")
                    result_msg.body = f"{product_name};{cheaper_store}"
                    await self.send(result_msg)
                else:
                    print("Nije moguće usporediti cijene jer proizvod ne postoji u jednom ili oba dućana.")

    async def setup(self):
        self.add_behaviour(self.ComparePricesBehaviour())

def extract_price(response):
    try:
        price_str = response.split()[-2]  # pretpostavljam da je cijena predzadnja riječ
        return float(price_str)
    except (IndexError, ValueError):
        return float('inf')  

class ListaAgent(Agent):
    class CreateShoppingListBehaviour(CyclicBehaviour):
        def __init__(self):
            super().__init__()
            self.dm_products = []
            self.bipa_products = []
            self.processed_count = 0 #brojač koji broji proizvode i resetira se nakon 6

        async def run(self):
            msg = await self.receive(timeout=10)  
            if msg:
                product, store = msg.body.split(";")
                if store == "Dm-u" and product not in self.dm_products:  #osigurava da se samo jednom ispiše proizvod na listu a ne dvaput
                    self.dm_products.append(product)
                elif store == "Bipi" and product not in self.bipa_products:
                    self.bipa_products.append(product)

                if len(self.dm_products) + len(self.bipa_products) >= 6: #ispis liste nakon 6 unosa
                    print(f"---Kupujte sljedeće proizvode u Dm-u: {self.dm_products}")
                    print(f"---Kupujte sljedeće proizvode u Bipi: {self.bipa_products}")
                    self.dm_products = []
                    self.bipa_products = []
                    self.processed_count = 0
                    #self.kill()  

    class HandleUnmatchedMessages(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                print(f"Primljena poruka za listu o proizvodu unmatched message: {msg.body}") 

    async def setup(self):
        self.add_behaviour(self.CreateShoppingListBehaviour())
        self.add_behaviour(self.HandleUnmatchedMessages())



async def main():
    lista_agent = ListaAgent("listagent@localhost", "listagent")  
    await lista_agent.start(auto_register=True)

    sender = SenderAgent("secondagent@localhost", "password")
    await sender.start(auto_register=True)
    store_agent = DmAgent("prviagent@localhost", "prviagent") 
    await store_agent.start(auto_register=True)

    sender2 = SenderAgent2("thirdagent@localhost", "password")  
    await sender2.start(auto_register=True)
    store_agent2 = BipaAgent("drugiagent@localhost", "drugiagent") 
    await store_agent2.start(auto_register=True)

    comparator_agent = ComparatorAgent("comparatoragent@localhost", "comparator")  
    await comparator_agent.start(auto_register=True)




if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program je prekinut.") #ovo je implementirano da se program ljepse zavrsi nakon ctrl+c
  
