#### tavily

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

#### serper

eb3c7892030d9be951ce06083106db4db378b84f

#### firecrawl

fc-831a5a876d8c471893a42fb2324cc42e

#### LLM API key有两个

##### EB5专用的：

curl --location 'https://qianfan.baidubce.com/v2/chat/completions'
--header 'Content-Type: application/json'
--header 'Authorization: Bearer bce-v3/ALTAK-mCOi62yEOQCJIvZVDI521/10000568a22b656d14d37bb80abb5da439026f1a'
--data '{
    "model": "ernie-5.0-thinking-preview",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "你好"
        }
    ]
}'

##### 其它模型统一用这个：

AGENT_MODEL_API_KEY=sk-HoI9K08JDDEvstxTk0nxZSTpLcePrpKfru2Ya7nOSIXGHCNu
AGENT_MODEL_BASE_URL=http://yy.dbh.baidu-int.com/v1
AGENT_MODEL_TIMEOUT=600
AGENT_ENABLE_REQUEST_LOGGING=false
可用模型：glm-4.5/gpt-5/doubao-seed-1-6-thinking-250615/gemini-2.5-pro/claude-sonnet-4-5-20250929

mini max的密钥：eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLotLnmmZPml60iLCJVc2VyTmFtZSI6Iui0ueaZk-aXrSIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxOTk4MDg2MDMwMzM0MzcwMDMyIiwiUGhvbmUiOiIxMzMyMTEwNTQ0MiIsIkdyb3VwSUQiOiIxOTk4MDg2MDMwMzMwMTc1NzI4IiwiUGFnZU5hbWUiOiIiLCJNYWlsIjoiIiwiQ3JlYXRlVGltZSI6IjIwMjUtMTItMDkgMTQ6NDU6MDgiLCJUb2tlblR5cGUiOjEsImlzcyI6Im1pbmltYXgifQ.Cduc9i-LTFkGZqXPTjE2O0bUlSNtM914e8889FxBCYyTOgM2GUWKSG0WmnmUlHajA7tEI_HoSQQusNuOpxun7GGEChsEE3moOYSWmYM43mRk3Vw4lp_L4DBTwSS14KlrO75O6FkiCIgiSIemxvPdb7iRZbLoT0DT5KK32qoXCgiZcyGnjsGKS0XLz8i0LA6oWIU0VNwJkp8AGjGp5Ul3UchqZNfqHsi71If-oPCEBfjekiib9kYtnr250zyomOwD1h9HDXw_-la68pY-a82fHBDXbEp9t3jF_cn1kR9YC4putmkoMnCxbIfHGIEEU5wGA2SQod1qlQLgtM5oT7VOBA
