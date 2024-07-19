import os
from operator import itemgetter


from dotenv import load_dotenv

from gnews import GNews


from bs4 import BeautifulSoup
from selenium import webdriver
import time
from selenium.webdriver.common.by import By

load_dotenv()
# prompt = ChatPromptTemplate.from_messages([
#     ("system", "You are world class technical documentation writer."),
#     ("user", "{input}")
# ])


class TrendAgent:
    def __init__(self, period="7d", max_results=10):
        """
        Initializes the TrendAgent class.

        This method sets up the FastAPI application, GNews client, and ChatOpenAI instance.
        It also defines the API endpoints and initializes the prompts for ChatOpenAI.

        Parameters:
            None

        Returns:
            None
        """
        self.google_news = GNews(period=period, max_results=max_results)
        # os.environ["LANGCHAIN_API_KEY"] = os.getenv("OPENAI_API_KEY")
        # os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

        # self.llm = ChatOpenAI()

        # self.app.get("/api/news/{topic}")(self.get_news)
        # self.app.get("/api/ask/{question}")(self.ask_openai)
        # self.app.get("/api/ask/{question}/{context}")(self.ask_openai)
        # self.app.get("/api/ask_relevant_trends/{topic}/{context}")(
        #     self.ask_relevant_trends
        # )

        # self.prompts = load_prompts_from_file("prompt/prompts.yml")

    # def add_documents(self, docs):
    #     """
    #     Add documents to the collection.

    #     Args:
    #         docs (list): List of documents to be added.
    #     """
    #     self.chroma_client.add_documents(docs)

    # def query(self, query):
    #     return self.chroma_client.similarity_search(query)

    # def load_prompts_from_file(self, filename: str):
    #     if not os.path.exists(filename):
    #         return {"error": "File does not exist"}

    #     with open(filename, 'r') as file:
    #         data = yaml.safe_load(file)

    #     prompts_dict = {}
    #     print(data)
    #     for prompt_name, prompt  in data['prompts'].items():
    #         system_message = ("system", ''.join(prompt['prompt']['system']))
    #         user_message = ("user", ''.join(prompt['prompt']['user']))
    #         prompts_dict[prompt_name] = {'prompt':ChatPromptTemplate.from_messages([system_message, user_message]),'variables':prompt['variables']}

    #     return prompts_dict

    # async def ask_relevant_trends(self, topic: str, context=None):
    #     await self.get_news(topic)
    #     news = self.query(topic)
    #     print(news)
    #     news = {news_["article"]["title"]: news_["article"]["text"] for news_ in news}
    #     output_parser = StrOutputParser()
    #     chain = self.prompts["get_trend_analysis"]["prompt"] | self.llm | output_parser
    #     print(chain)
    #     response = [
    #         chain.invoke({"title": title, "content": content, "context": context})
    #         for title, content in news.items()
    #     ]
    #     return response

    def get_news(self, topic: str):
        """
        Retrieves news related to the specified topic.

        Args:
            topic (str): The topic to search for news.

        Returns:
            dict: A dictionary containing the news data, or an error message if failed to get news.
        """
        data_ = self.google_news.get_news(topic)
        data = []
        for news in data_:
            print("--------------------------------")
            try:
                url = news["url"]
                article = self.google_news.get_full_article(url)
                news["article"] = {
                    "title": article.title,
                    "text": article.text,
                }
                data.append(news)
                print(f"Downloaded article: {article.title}")
            except Exception as e:
                print(e)
        return data

    def get_news(self, topic: str):
        """
        Retrieves news related to the specified topic.

        Args:
            topic (str): The topic to search for news.

        Returns:
            dict: A dictionary containing the news data, or an error message if failed to get news.
        """
        data_ = self.google_news.get_news(topic)
        data = []
        for news in data_:

            try:
                url = news["url"]
                article = self.google_news.get_full_article(url)
                news["article"] = {
                    "title": article.title,
                    "text": article.text,
                }
                data.append(news)
                # print(f"Downloaded article: {article.title}")
            except Exception as e:
                print(e)
        return data

    def get_news_by_topic(self, category: str):
        assert category in [
            "WORLD",
            "NATION",
            "BUSINESS",
            "TECHNOLOGY",
            "ENTERTAINMENT",
            "SPORTS",
            "SCIENCE",
            "HEALTH",
        ]
        data_ = self.google_news.get_news_by_topic(category)
        data = []
        for news in data_:
            print("----------------topic----------------")
            try:
                url = news["url"]
                article = self.google_news.get_full_article(url)
                news["article"] = {
                    "title": article.title,
                    "text": article.text,
                }
                data.append(news)
                print(f"Downloaded article: {article.title}")
            except Exception as e:
                print(e)
        return data

    def get_news_by_site(self, site: str):
        """
        Retrieves news related to the specified topic.

        Args:
            topic (str): The topic to search for news.

        Returns:
            dict: A dictionary containing the news data, or an error message if failed to get news.
        """
        data_ = self.google_news.get_news_by_site(site)
        print(data_)
        data = []
        for news in data_:
            print("----------------site----------------")
            try:
                url = news["url"]
                article = self.google_news.get_full_article(url)
                news["article"] = {
                    "title": article.title,
                    "text": article.text,
                }
                data.append(news)
                print(f"Downloaded article: {article.title}")
            except Exception as e:
                print(e)
        return data

        # if data:
        #     self.add_documents(
        #         [
        #             {
        #                 "metadata": {
        #                     "title": news["article"]["title"],
        #                     "summary": news["article"]["summary"],
        #                 },
        #                 "data": news["article"]["text"],
        #             }
        #             for news in data
        #         ]
        #     )
        #     return data
        # else:
        #     return JSONResponse(content={"error": "Failed to get news"})

    # def summarize_article(self, title: str, content: str):
    #     """
    #     Summarizes the specified article.

    #     Args:
    #         article (str): The article to summarize.

    #     Returns:
    #         str: The summarized article.
    #     """
    #     output_parser = StrOutputParser()
    #     print(f"Prompt: {self.prompts}")
    #     chain = self.prompts["summarize_article"]["prompt"] | self.llm | output_parser
    #     response = chain.invoke({"title": title, "content": content})
    #     print(f"Summary: {response}")
    #     return response

    # def get_prompts_from_template(self, template):
    #     prompts_dict = {}
    #     for message in template.messages:
    #         role, content = message
    #         if role == "user":
    #             prompts_dict[content] = template.format(input=content)
    #     return prompts_dict

    # async def ask_openai(self, question: str, context=None):
    #     output_parser = StrOutputParser()
    #     chain = self.prompt | self.llm | output_parser
    #     response = chain.invoke({"input": question})
    #     return response

    # async def get_context_about_topic(self, topic: str):
    #     news = await self.get_news(topic)
    #     question = f"Can you provide more context about the recent news on {topic}?"
    #     context = await self.ask_openai(question)
    #     return {"news": news, "context": context}

    def get_company_description(self, companyURL):
        driver = webdriver.Chrome()
        driver.get(companyURL)
        driver.find_element(
            By.XPATH, "/html/body/div[5]/div/div/section/button"
        ).click()
        time.sleep(2)

    def get_linkedin_feed(self, companyURL="https://uk.linkedin.com/company/nag/"):

        # target_url = "https://www.linkedin.com/company/nag/"
        driver = webdriver.Chrome()
        driver.get(companyURL)
        # Close the popup
        driver.find_element(
            By.XPATH, "/html/body/div[5]/div/div/section/button"
        ).click()
        time.sleep(2)

        for _ in range(20):
            try:
                # Action scroll down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            except:
                time.sleep(1)

        resp = driver.page_source
        driver.close()

        soup = BeautifulSoup(resp, "html.parser")
        try:
            # Get all the posts
            # data-test-id="main-feed-activity-card__commentary"
            # data-test-id="about-us__description"
            # description = soup.find_all("p",{"data-test-id":"about-us__description"})
            times = soup.find_all("time", {"class": "flex-none"})
            text = soup.find_all(
                "p", {"data-test-id": "main-feed-activity-card__commentary"}
            )
            feed = [
                (x.text, t.text.translate({ord(i): None for i in " \n\ "}))
                for t, x in zip(times, text)
            ]
        except:
            feed = None
        return feed

        for _ in range(20):
            try:
                # Action scroll down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            except:
                time.sleep(1)

        # no_of_pagedowns = 50
        # elem = driver.find_element(By.TAG_NAME,"body")
        # while no_of_pagedowns:
        #     elem.send_keys(Keys.PAGE_DOWN)
        #     time.sleep(0.5)
        #     no_of_pagedowns-=1

        resp = driver.page_source
        driver.close()
        soup = BeautifulSoup(resp, "html.parser")
        try:
            # Get all the posts
            # data-test-id="main-feed-activity-card__commentary"

            times = soup.find_all("time", {"class": "flex-none"})
            text = soup.find_all(
                "p", {"data-test-id": "main-feed-activity-card__commentary"}
            )
            feed = [
                (x.text, t.text.translate({ord(i): None for i in " \n\ "}))
                for t, x in zip(times, text)
            ]
        except:
            feed = None
        return feed


if __name__ == "__main__":
    agent = TrendAgent()
    for n, t in agent.get_linkedin_feed(
        "https://uk.linkedin.com/company/yellowdog-limited"
    ):
        print(f"Time: {t}")
        print(f"News: {n}")

    # uvicorn.run(agent.app, host="
