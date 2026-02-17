import pandas as pd
import streamlit as st
from typing import Optional
from google.cloud import bigquery
from google.oauth2 import service_account
from langchain_core.tools import Tool, StructuredTool
from pydantic import BaseModel, Field
from src.code_interpreter import CodeInterpreterClient


class SqlTableInfoInput(BaseModel):
    table_name: str = Field()


class ExecSqlInput(BaseModel):
    query: str = Field()
    limit: Optional[int] = Field(default=None)


class BigQueryClient:
    """
    BigQuery 클라이언트 (Responses API 기반)

    Assistants API에서 Responses API로 마이그레이션된 Code Interpreter를 사용합니다.
    """
    def __init__(
        self,
        code_interpreter: CodeInterpreterClient,
        project_id: str = "youtube-api-client-480202",  ## 이 부분은 자신이 등록한 구글 클라우드 프로젝트 이름으로 변경
        # "bigquery-public-data"란?
        # Google이 공개해 둔 "공공 데이터(public dataset)"
        # Google Trends(검색 트렌드) 데이터
        # 국가별 급상승 검색어
        # 주차(week), 점수(score), 검색어(term) 등
        dataset_project_id: str = "bigquery-public-data",
        dataset_id: str = "google_trends",
    ) -> None:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        self.client = bigquery.Client(credentials=credentials, project=project_id)
        self.dataset_project_id = dataset_project_id
        self.dataset_id = dataset_id
        self.table_names_str = self._fetch_table_names()
        self.code_interpreter = code_interpreter

    def _fetch_table_names(self) -> str:
        """
        BigQuery에서 이용 가능한 테이블명을 가져옴
        쉼표로 구분된 문자열로 반환
        """
        query = f"""
        SELECT table_name
        FROM `{self.dataset_project_id}.{self.dataset_id}.INFORMATION_SCHEMA.TABLES`
        """
        table_names = self._exec_query(query).table_name.tolist()
        return ", ".join(table_names)

    def _exec_query(self, query: str, limit: int = None) -> pd.DataFrame:
        """SQL을 실행하여 Pandas DataFrame으로 반환"""
        if limit is not None:
            query += f"\nLIMIT {limit}"
        query_job = self.client.query(query)
        return query_job.result().to_dataframe(create_bqstorage_client=True)

    def exec_query_and_upload(self, query: str, limit: int = None) -> str:
        """
        Execute given SQL query and return result as a formatted string or path to a saved file.

        Responses API 기반으로 업데이트됨: 파일 업로드 경로가 Container 기반으로 변경
        """
        try:
            df = self._exec_query(query, limit)
            csv_data = df.to_csv().encode("utf-8")
            file_id = self.code_interpreter.upload_file(csv_data)
            # Responses API에서는 Container를 사용하므로 파일 경로가 다를 수 있음
            return f"sql:\n```\n{query}\n```\n\nsample results:\n{df.head()}\n\nfull result was uploaded with File ID: {file_id} (accessible in Code Interpreter)"
        except Exception as e:
            return f"SQL execution failed. Error message is as follows:\n```\n{e}\n```"

    def _generate_sql_for_table_info(self, table_name: str) -> tuple:
        """지정된 테이블의 스키마와 샘플 데이터를 가져오는 SQL 생성"""
        get_schema_sql = f"""
        SELECT
            TO_JSON_STRING(
                ARRAY_AGG(
                    STRUCT(
                        IF(is_nullable = 'YES', 'NULLABLE', 'REQUIRED'
                    ) AS mode,
                    column_name AS name,
                    data_type AS type
                )
                ORDER BY ordinal_position
            ), TRUE) AS schema
        FROM
            `{self.dataset_project_id}.{self.dataset_id}.INFORMATION_SCHEMA.COLUMNS`
        WHERE
            table_name = "{table_name}"
        """

        sample_data_sql = f"""
        SELECT
            *
        FROM
            `{self.dataset_project_id}.{self.dataset_id}.{table_name}`
        LIMIT
            3
        """
        return get_schema_sql, sample_data_sql

    def get_table_info(self, table_name: str) -> str:
        """테이블 스키마와 샘플 데이터를 반환"""
        get_schema_sql, sample_data_sql = self._generate_sql_for_table_info(table_name)
        schema = self._exec_query(get_schema_sql).to_string(index=False)
        sample_data = self._exec_query(sample_data_sql).to_string(index=False)
        table_info = f"""
        ### schema
        ```
        {schema}
        ```

        ### sample_data
        ```
        {sample_data}
        ```
        """
        return table_info

    def exec_query_tool(self):
        exec_query_tool_description = f"""
        BigQuery에서 SQL 쿼리를 실행하는 도구입니다.
        SQL 쿼리를 입력하면 BigQuery에서 실행됩니다.

        이 도구를 사용하기 전에 `get_table_info_tool` 도구로
        테이블 스키마를 확인하는 것을 **강력히** 권장합니다.

        BigQuery용 쿼리를 작성할 때는
        project_id, dataset_id, table_id를 반드시 지정해야 합니다.

        현재 사용 중인 BigQuery는 다음과 같습니다:
        - project_id: {self.dataset_project_id}
        - dataset_id: {self.dataset_id}
        - table_id: {self.table_names_str}

        SQL은 가독성을 고려해 작성해주세요 (예: 줄바꿈 등을 포함).
        최빈값을 구할 때는 "Mod" 함수를 사용해주세요.

        샘플 외의 전체 결과는 Code Interpreter에 CSV 파일로 저장됩니다.
        Code Interpreter에서 Python을 실행하여 접근할 수 있습니다.
        (Responses API 기반)
        """
        return StructuredTool.from_function(
            name="exec_query",
            func=self.exec_query_and_upload,
            description=exec_query_tool_description,
            args_schema=ExecSqlInput,
        )

    def get_table_info_tool(self):
        sql_table_info_tool_description = f"""
        BigQuery 테이블의 스키마와 샘플 데이터(3행)를 가져오는 도구
        SQL 쿼리를 작성할 때 테이블 스키마를 참조할 수 있음

        이용 가능한 테이블은 다음과 같습니다: {self.table_names_str}
        """
        return Tool.from_function(
            name="sql_table_info",
            func=self.get_table_info,
            description=sql_table_info_tool_description,
            args_schema=SqlTableInfoInput,
        )
