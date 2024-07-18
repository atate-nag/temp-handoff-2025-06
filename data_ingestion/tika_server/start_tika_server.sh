#!/bin/bash
export TIKA_SERVER_JAR = ${PWD}
TIKA_SERVER_JAR = 'PATH_OF_FOLDER_CONTAINING_TIKA_SERVER_JAR'.
java -jar tika-server-standard-2.9.2.jar --port 9999 &