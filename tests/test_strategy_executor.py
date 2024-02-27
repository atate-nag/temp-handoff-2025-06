import pytest
import strategy_executor
import core_components
import os


def test_trend_analysis():
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    mock_market_insights = []
    
    trend_results = strategy_executor.trend_analysis(mock_client, mock_market_insights)
    assert trend_results == []
    
    # mock_overseer_manage_assistant = mocker.patch('strategy_executor.overseer_manage_assistant')
    # mock_client = mocker.MagicMock()
    # mock_market_insights = mocker.MagicMock()
    # mock_company_data = mocker.MagicMock()

    # strategy_executor.trend_analysis(mock_client, mock_market_insights)

    # mock_overseer_manage_assistant.assert_called_once_with(
    #     mock_client, 
    #     strategy_executor.run_trends_analysis, 
    #     mock_market_insights,
    #     mock_company_data
    # )

def test_capabilities_analysis(mocker):
    mock_overseer_manage_assistant = mocker.patch('strategy_executor.overseer_manage_assistant')
    mock_client = mocker.MagicMock()
    mock_company_insights = mocker.MagicMock()
    mock_company_data = mocker.MagicMock()

    strategy_executor.capabilities_analysis(mock_client, mock_company_insights)

    mock_overseer_manage_assistant.assert_called_once_with(
        mock_client, 
        strategy_executor.run_capabilities_analysis, 
        mock_company_insights,
        mock_company_data
    )