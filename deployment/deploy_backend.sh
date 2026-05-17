DIR_PATH=/Users/mousommondal/projects/sci-bowl
if [ "$PWD" != "$DIR_PATH" ]; then
  echo "Run the deployment from $DIR_PATH"
  exit 1
fi


rsync -a src/ lambda/src/
sam build --profile onasmmon
sam deploy --profile onasmmon

