<?php

include './config.php';

set_time_limit(0);

$start_time = time();

$customer_id = htmlspecialchars($_GET['customer_id']);
$target_date = htmlspecialchars($_GET['target_date']);

//echo '[Info] customer_id: ' . $customer_id . "\n";
//echo '[Info] target_date: ' . $target_date . "\n";

// 対象日のクエリログが格納されているのは、次の日の日付の名前がついたファイル。
// なぜなら、深夜0時をすぎると現在のログがログローテートされるから。
// 日付が変わる付近のログは、どっちに入るか微妙になっている。
$file_time = strtotime('+1 day', strtotime($target_date));
$file_date = date('Ymd', $file_time);
//echo '[Info] file_date: ' . $file_date . "\n";

// コマンド実行部分
$cmd = PATH_TO_PYTHON
     . ' ' . PATH_TO_LIB . '/query-log-tracer/trace.py'
     . ' --log-file=' . PATH_TO_LOG . '/query.log-%s.gz'
     . ' --target-table=dtb_customer'
     . ' --target-column=point'
     . ' --filter-column=customer_id'
     . ' --filter-value=%d';
$command = sprintf($cmd, escapeshellcmd($file_date), escapeshellcmd($customer_id));

exec($command, $output, $return_var);

// '=== Summary ===' 以降の行のみ抜き出す
$results = array();
$reached = false;
foreach ($output as $line) {
    if ($line === '=== Summary ===') {
        $reached = true;
        continue;
    }
    if ($reached) {
        array_push($results, $line);
    }
}

$finish_time = time();
$execution_time = $finish_time - $start_time;

// 結果出力部分
if ($return_var !== 0) {
    echo 'Error: ' . $return_var . "\n";
} else if (count($results) === 0) {
    echo "No results in this day.\n";
} else {
    echo implode("\n", $results) . "\n";
}
echo "\n(execution time: " . $execution_time . " sec)\n";
