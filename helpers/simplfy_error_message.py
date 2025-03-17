



class SimplifyErrorMessageRepository:

    @staticmethod
    def simplify_sql_error_message(error_message: str) -> str:
        """
        Simplify SQL error messages by extracting the relevant parts.
        Returns a formatted error message in the format: <error_description> [SQL: <sql_query>]
        """
        # Extract the error description (between the first colon and "[SQL:")
        if ": " in error_message and "[SQL:" in error_message:
            error_description = error_message.split(": ")[1].split("[SQL:")[0].strip()
            sql_query = error_message.split("[SQL:")[1].split("]")[0].strip()
            return f"{error_description} [SQL: {sql_query}]"

        # Fallback: Return the original error message if parsing fails
        return error_message