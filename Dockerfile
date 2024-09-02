# Use the official Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose the port
EXPOSE 8080

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
