#!/bin/sh
CMD=${CMD:-python3}
ARGS=${ARGS:-$@}
exec $CMD $ARGS
