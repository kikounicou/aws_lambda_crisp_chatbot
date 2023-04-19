import json
import http.client
import os
import openai
import pinecone


def lambda_handler(event, context):
    CRISP_API_KEY = os.environ['CRISP_API_KEY']
    print(event)
    # Extraire les informations du JSON
    body = json.loads(event['body'])
    data = body['data']
    website_id = data['website_id']
    session_id = data['session_id']
    fingerprint = data['fingerprint']
    content = data['content']
    
   
    # Appeler l'API CRISP pour récupérer les conversations de la session en cours
    conn = http.client.HTTPSConnection("api.crisp.chat")
    payload = ''
    headers = {
      'Authorization': '<YOUR CRISP API KEY>',
      'X-Crisp-Tier': 'plugin'
    }
    conversation_endpoint = "/v1/website/" + body["website_id"] + "/conversation/" + session_id
    conn.request("GET", conversation_endpoint, payload, headers)
    res = conn.getresponse()
    conversation_data = res.read()
    conversation = json.loads(conversation_data.decode("utf-8"))
    

    conn = http.client.HTTPSConnection("app.crisp.chat")
    payload = json.dumps({
        "from": "operator",
        "type": "start",
        "stealth": False
    })
    
    # Start composing a message in the conversation
    headers = {
        'Authorization': '<YOUR CRISP API KEY>',
        'Content-Type': 'application/json'
    }
    conn.request("PATCH", "/api/v1/website/"+website_id+"/conversation/"+session_id+"/compose", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))

    # Définir la clé API en tant que variable d'environnement
    os.environ["OPENAI_API_KEY"] = "<Your OpenAI API Key>"
    embed_model = "text-embedding-ada-002"
    index_name = '<YOUR PINECONE INDEX NAME>'
    
    # initialize connection to pinecone
    pinecone.init(
        api_key="<Your Pinecone API Key>",  # app.pinecone.io (console)
        environment="<YOUR PINECONE ENVIRONMENT>"  # next to API key in console
    )
    
    index = pinecone.Index(index_name)
    
    # Initialiser la clé API
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    query = content

    
    res = openai.Embedding.create(
        input=[query],
        engine=embed_model
    )
    
    # retrieve from Pinecone
    xq = res['data'][0]['embedding']
    
    # get relevant contexts (including the questions)
    res = index.query(xq, top_k=5, include_metadata=True)
            
    
    print(res)
    
    # Lister les URLs à inclure dans la réponse
    matches = res.get("matches", [])
    url_list = [f"{item['metadata']['url']}" for item in matches]
    url_list_str = "- " + "\n- ".join(url_list)
    
    
    
    # get list of retrieved text
    contexts = [item['metadata']['text'] for item in res['matches']]
    
    augmented_query = "\n\n---\n\n".join(contexts)+"\n\n-----\n\n"+query
    
    print(augmented_query)
    

    # system message to 'prime' the model
    primer = f"""A highly intelligent system that answers
user questions based on the information provided by the user above
each question. If the information can not be found in the information
provided by the user you truthfully just reply "STOP". Answer in the language of the question.".
            """

    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": primer},
            {"role": "user", "content": augmented_query}
        ]
    )
    
    
    markdown_content = res['choices'][0]['message']['content']
    
    print(markdown_content)
    
    conn = http.client.HTTPSConnection("api.crisp.chat")
            
            
            
    if "STOP" in markdown_content:
        response_content = "Je n'ai pas trouvé de réponse dans notre base de connaissance. Un conseiller reviendra vers vous au plus vite. Vous recevrez également copie de notre réponse à l'adresse nicou@mymail.be"
    else:
        response_content = f"{markdown_content} \n\n*Cette réponse a été générée automatiquement sur base des sources suivantes:*\n{url_list_str}"
    
    payload = json.dumps({
        "type": "text",
        "from": "operator",
        "origin": "urn:nicolas.deswysen:union-des-villes-et-communes-de-wallonie:0",
        "user": {
            "type": "participant",
            "nickname": "Bot",
            "avatar": "https://cdn.pixabay.com/photo/2017/10/24/00/39/bot-icon-2883144_1280.png"
        },
        "content": response_content
    })
    
    
    headers = {
        'Authorization': '<YOUR CRISP API KEY>',
        'Content-Type': 'application/json',
        'X-Crisp-Tier': 'plugin'
    }
    conn.request("POST", "/v1/website/"+website_id+"/conversation/"+session_id+"/message", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))
            
    
    
    # Renvoyer une réponse HTTP 200 OK pour confirmer la réception des données
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({'message': 'Webhook received'})
    }
