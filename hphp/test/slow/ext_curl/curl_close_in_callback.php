<?php
$handle = curl_init("https://www.facebook.com");
curl_setopt($handle, CURLOPT_HEADERFUNCTION, function($handle, $header) {
        curl_close($handle);
});
curl_exec($handle);