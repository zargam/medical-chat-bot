FROM python:3.10-slim-buster

WORKDIR /app

COPY . /app

RUN pip install -r requirements.txt

# Chunks create karne ke liye sirf ek baar script run karo
RUN python3 store_index.py

#everyTimerun
CMD ["python3", "app.py"]
