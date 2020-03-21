<pre>

$ docker run -it --rm \
    --name db \
    -e POSTGRES_DB=djangosample \
    -e POSTGRES_USER=sampleuser \
    -e POSTGRES_PASSWORD=samplesecret \
    postgres:9.6.1

$ docker run -it --rm \
    -p 8000:8000 \
    --link db \
    -e DJANGO_DB_HOST=db \
    -e DJANGO_DEBUG=True \
    django-sample \
    ./manage.py runserver 0:8000

</pre>
    
