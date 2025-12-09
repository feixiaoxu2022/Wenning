curl --location 'http://hostname/v1/models/gemini-3-pro-preview' \

--header 'Authorization: $sk' \

--header 'Content-Type: application/json' \

--data '{

    "contents": [

    {

    "role": "user",

    "parts": [

    {

    "text": "The weather in Chicago this weekend"

    }

    ]

    }

    ],

    "tools": [

    {

    "googleSearch": {}

    }

    ]

}'

﻿google API官方文档：https://ai.google.dev/api/generate-content?hl=zh-cn#method:-models.generatecontent

https://ai.google.dev/gemini-api/docs/text-generation?hl=zh-cn#multi-turn-conversations
