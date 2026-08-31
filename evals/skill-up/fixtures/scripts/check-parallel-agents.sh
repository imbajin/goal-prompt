#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
normalized_message="${message//$'\n'/ }"
if printf '%s' "$normalized_message" | grep -Eqi '(没有|不设|不指定|未指定|不存在|无需|缺少|缺乏|无)[^。.]*(唯一[^。.]*(写入|writer|owner|负责人|所有者)|single owner)|(^|[^[:alnum:]_])(no|without)[[:space:]]+[^.]*(single|unique)[[:space:]]+(owner|writer)|(lack|missing|do not have|does not have)[^.]*(single|unique)[[:space:]]+(owner|writer)|not[[:space:]]+(assigned[[:space:]]+to|owned[[:space:]]+by)[^.]*(single|unique)[[:space:]]+(owner|writer)|multiple[[:space:]]+(owners|writers)[^.]*rather[[:space:]]+than[^.]*(single|unique)[[:space:]]+(owner|writer)|(schema|lockfile|共享)[^。.]*(multiple|several|two|多个|多名|两个|共同|联合|co-owned|jointly owned)[^。.]*(owners?|writers?|负责人|写入者|agent)|(multiple|several|two|多个|多名|两个)[^。.]*(owners?|writers?|负责人|写入者|agent)[^。.]*(schema|lockfile|共享)|(schema|lockfile|共享)[^。.]*(may also|can also|也可|也能|也可以)[^。.]*(modify|edit|write|修改|编辑|写入)|(any agent|任意 agent|任何 agent)[^。.]*(modify|edit|write|修改|编辑|写入)[^。.]*(schema|lockfile|共享)|(schema|lockfile|共享)[^。.]*(advisory only|仅供参考|非强制)|(schema|lockfile|共享)[^。.]*(writable|editable|modifiable|可写|可编辑|可修改)[^。.]*(by[[:space:]]+)?(all|every|any)[[:space:]]+(agents?|workers?)|(schema|lockfile|共享)[^。.]*(but|except|however|但|不过|除外)[^。.]*(auth|billing|notifications|another agent|other agent|all agents|every agent|everyone|other workers?|non-owners?|另一个 agent|其他 agent|所有 agent|全部 agent|每个 agent|非 owner)[^。.]*(may|can)[[:space:]]+(modify|edit|write)|(another agent|other agent|all agents|every agent|everyone|other workers?|non-owners?|另一个 agent|其他 agent|所有 agent|全部 agent|每个 agent|非 owner)[^。.]*(may|can)[[:space:]]+(modify|edit|write)[^。.]*(it|schema|lockfile|共享)|(another agent|other agent|all agents|every agent|everyone|other workers?|non-owners?|另一个 agent|其他 agent|所有 agent|全部 agent|每个 agent|非 owner)[^。.]*(allowed|permitted|authorized|(has|have) permission|允许|获准|授权)[^。.]*(modify|edit|write|修改|编辑|写入)'; then
  echo "shared files require one explicit owner" >&2
  exit 1
fi
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi 'auth'
printf '%s' "$message" | grep -Eqi 'billing'
printf '%s' "$message" | grep -Eqi 'notifications'
printf '%s' "$message" | grep -Eqi 'ownership|owner|所有权|归属'
printf '%s' "$message" | grep -Eqi '(schema|lockfile|共享).*(single owner|unique owner|only owner|single writer|unique writer|only writer|唯一 owner|唯一 writer|唯一文件 owner|唯一归属|唯一拥有|独占|唯一负责人|唯一负责|唯一可修改|唯一可以修改|唯一写入|唯一的共享|唯一 (schema|dependency) owner)|(single owner|unique owner|only owner|single writer|unique writer|only writer|唯一 owner|唯一 writer|唯一文件 owner|唯一归属|唯一拥有|独占|唯一负责人|唯一负责|唯一可修改|唯一可以修改|唯一写入|唯一的共享|唯一 (schema|dependency) owner).*(schema|lockfile|共享)'
printf '%s' "$message" | grep -Eqi '(integrat|接缝|集成).*(re-run|rerun|复跑|复验|重新运行|重跑|再次运行)|(re-run|rerun|复跑|复验|重新运行|重跑|再次运行).*(integrat|接缝|集成)'
printf '%s' "$message" | grep -Eqi 'independent reviewer|独立.*(reviewer|审查|评审)'
