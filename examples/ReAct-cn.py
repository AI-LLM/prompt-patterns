# Author: Wei Lu (mailwlu@gmail.com)
# based on https://til.simonwillison.net/llms/python-react-pattern
# This code is Apache 2 licensed:
# https://www.apache.org/licenses/LICENSE-2.0
import openai
import re
import httpx
import os

openai.api_key = os.environ['OPENAI_API_KEY']
 
class ChatBot:
    def __init__(self, system=""):
        self.system = system
        self.messages = []
        if self.system:
            self.messages.append({"role": "system", "content": system})
    
    def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result
    
    def execute(self):
        completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=self.messages)
        # Uncomment this to print out token usage each time, e.g.
        # {"completion_tokens": 86, "prompt_tokens": 26, "total_tokens": 112}
        # print(completion.usage)
        return completion.choices[0].message.content

prompt = """
每当你被问到一个问题时，你使用一次或多次Thought, Action, 停止输出, 获得Observation输入的循环来获得足够的信息，最后回答问题。
使用Thought来描述你对于问题的想法。
使用Action来获取需要的信息。然后停止输出，等待我给你输入以Observation开始的信息。

你可用的action包括：

calculate:
e.g. calculate: 4 * 7 / 3
用以获取数学计算的结果

wikipedia:
e.g. wikipedia: Django
用以查找人物、地点、事物的介绍

news_search:
e.g. news_search: Django
用以查找最新的新闻、事件，输入参数应为英文

用此方法回答问题的过程例子如下：
===
>我问问题：
现任英国首相是谁？

>你输出：
Thought: I should look up Prime minister of UK in news
Action: news_search: Prime minister of UK

>你停止输出

>我给你输入：
Observation: Rishi Sunak, Prime minister of UK, is visiting the US.

>然后你能够回答问题：
Answer: 现任英国首相是Rishi Sunak。
===
>我问问题：
What is the capital of France?

>你输出：
Thought: I should look up France on Wikipedia
Action: wikipedia: France

>你停止输出

>我给你输入：
Observation: France is a country. The capital is Paris.

>然后你能够回答问题：
Answer: The capital of France is Paris
===
""".strip()


action_re = re.compile('^Action: (\w+): (.*)$')

def query(question, max_turns=10):
    i = 0
    bot = ChatBot(prompt)
    next_prompt = question
    while i < max_turns:
        i += 1
        result = bot(next_prompt)
        print(result)
        actions = [action_re.match(a) for a in result.split('\n') if action_re.match(a)]
        if actions:
            # There is an action to run
            action, action_input = actions[0].groups()
            if action not in known_actions:
                raise Exception("Unknown action: {}: {}".format(action, action_input))
            print(" -- running {} {}".format(action, action_input))
            observation = known_actions[action](action_input)
            print("Observation:", observation)
            next_prompt = "Observation: {}".format(observation)
        else:
            return


def wikipedia(q):
    return httpx.get("https://en.wikipedia.org/w/api.php", params={
        "action": "query",
        "list": "search",
        "srsearch": q,
        "format": "json"
    }).json()["query"]["search"][0]["snippet"]


def simon_blog_search(q):
    results = httpx.get("https://datasette.simonwillison.net/simonwillisonblog.json", params={
        "sql": """
        select
          blog_entry.title || ': ' || substr(html_strip_tags(blog_entry.body), 0, 1000) as text,
          blog_entry.created
        from
          blog_entry join blog_entry_fts on blog_entry.rowid = blog_entry_fts.rowid
        where
          blog_entry_fts match escape_fts(:q)
        order by
          blog_entry_fts.rank
        limit
          1""".strip(),
        "_shape": "array",
        "q": q,
    }).json()
    return results[0]["text"]

def calculate(what):
    return eval(what)

def news_search(q):
    return httpx.get("https://gnews.io/api/v4/search", params={
        "q": q,
        "max": 1,
        "lang": "en",
        "apikey": os.environ["NEWS_API_KEY"]
    }).json()["articles"]

known_actions = {
    "wikipedia": wikipedia,
    "calculate": calculate,
    "simon_blog_search": simon_blog_search,
    "news_search": news_search
}

query("最新一届足球世界杯冠军是？")