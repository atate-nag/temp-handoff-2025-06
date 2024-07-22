import os
from operator import itemgetter
import requests, json

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


class LinkedinAgent:
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
    
    def get_linkedin_url_company(self, company):
        try:
            search = company + " linkedin"
            url = "https://www.google.com/search"

            headers = {
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.5",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82",
            }
            # user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/124.0"
            # headers = {'User-Agent': user_agent,'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'}

            parameters = {"q": search}

            content = requests.get(url, headers=headers, params=parameters).text
            soup = BeautifulSoup(content, "html.parser")
            # print(soup)
            search = soup.find(id="search")
            # print(search)
            first_link = search.find("a")  # .replace('www.linkedin.com', 'uk.linkedin.com')

            return first_link["href"].replace("www.linkedin.com", "uk.linkedin.com")
        except Exception as e:
            return "fail"


if __name__ == "__main__":
    agent = LinkedinAgent()
    for n, t in agent.get_linkedin_feed(
        "https://uk.linkedin.com/company/yellowdog-limited"
    ):
        print(f"Time: {t}")
        print(f"News: {n}")

    # uvicorn.run(agent.app, host="
