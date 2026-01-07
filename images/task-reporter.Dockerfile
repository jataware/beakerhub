FROM base AS task-reporter

COPY --from=config bin/task-reporter.py /usr/local/bin/task-reporter.py

ENV CMD="python3"
ENV ARGS="/usr/local/bin/task-reporter.py"
