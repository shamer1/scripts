# AWS Events App

This Python application retrieves all scheduled EC2 and EBS events in AWS using provided credentials.

## Project Structure

```
aws-events-app
├── src
│   ├── main.py          # Entry point of the application
│   └── utils
│       └── aws_events.py # Utility functions for AWS interactions
├── requirements.txt     # Project dependencies
└── README.md            # Project documentation
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd aws-events-app
   ```

2. **Create a virtual environment (optional but recommended):**
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install the required dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Configure your AWS credentials:**
   Ensure that your AWS credentials are set up in `~/.aws/credentials` or through environment variables.

## Usage

To run the application and retrieve scheduled EC2 and EBS events, execute the following command:

```
python src/main.py
```

## Example Output

The application will output the scheduled EC2 and EBS events retrieved from your AWS account.

## License

This project is licensed under the MIT License.