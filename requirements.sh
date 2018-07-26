#! bin/bash

declare -a pip_installs=("oauth2client" "httplib2" "google-api-python-client"
												 "numpy" "scipy" "scikit-learn", "matplotlib"
												)

for i in "${pip_installs[@]}"
do
  pip install --upgrade $i
done

echo "END"
