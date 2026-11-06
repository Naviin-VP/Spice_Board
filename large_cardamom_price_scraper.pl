$ENV{'PERL_LWP_SSL_VERIFY_HOSTNAME'} = 0;
use strict;
use LWP::UserAgent;
use HTML::Entities;
use HTTP::Cookies;
use URI::Escape;
use URI::URL;
use Text::Unidecode;
use Encode;
use utf8;
use Encode;
use Sys::Hostname;
use Socket;
use Date::Calc qw/Date_to_Text Add_Delta_Days Today/;
use DateTime::Format::Strptime;
use DateTime;
use IO::Socket::SSL;

my $fmt = '%Y-%m-%dT%H:%M:%S';
my $parser = DateTime::Format::Strptime->new(pattern => $fmt);

my $ua = new LWP::UserAgent;
my $cookie_jar = HTTP::Cookies->new(file=>$0."_cookie.txt",autosave => 1,);
$ua->cookie_jar($cookie_jar);
$ua->agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36");
$ua->ssl_opts(verify_hostname => 0, SSL_verify_mode => IO::Socket::SSL::SSL_VERIFY_NONE);
$ua->max_redirect('7');

(my $cu_date=DateTime->now())=~s/([^>]+?T\d+)\:.+$/$1/igs;
my $Script_Log = "Script_Startlog"."_"."$cu_date.txt";
my $curdatetime=DateTime->now();
$curdatetime=~s/T/ /igs;

my $ips = get_public_ip ();
print "$ips\n";

my $filename="IndianSpices_Cardamon_Daily_Prices.txt";

open(FH,">$filename");
print FH "Date of Production\tS.NO\tDate of Auction\tMarket\tType\tPrice Per Kg\tIP Address\tCache Name\n";
close FH;
my $starting_page="https://www.indianspices.com/marketing/price/domestic/daily-price-large.html";
my $home_url="https://www.indianspices.com/marketing/price/domestic/daily-price-large.html";
my %headers=('accept'=>'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7","accept-language'=>'en-US,en;q=0.9","connection'=>'keep-alive","host'=>'www.indianspices.com","sec-ch-ua'=>'"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"","sec-ch-ua-mobile'=>'?0","sec-ch-ua-platform'=>'"Windows"","sec-fetch-dest'=>'document","sec-fetch-mode'=>'navigate","sec-fetch-site'=>'none","sec-fetch-user'=>'?1","upgrade-insecure-requests'=>'1","user-agent'=>'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36');
my $HomeContent=&GetContent($home_url,'GET',\%headers);
my $Cache_name="Home_Content.html";
open(FH,">Home_Content.html");
print FH $HomeContent;
close FH;
my $page=1;
start:
    while($HomeContent=~m/<tr[^>]*?>\s*<td[^>]*?>\s*(\d+)\s*<\/td>\s*<td[^>]*?>([\W\w]*?)<\/td>\s*<td[^>]*?>([\W\w]*?)<\/td>\s*<td[^>]*?>([\W\w]*?)<\/td>\s*<td[^>]*?>([\W\w]*?)<\/td>\s*<\/tr>/igs)
    {
        my ($sno,$date_of_auction,$market,$type,$price_per_kg)=($1,$2,$3,$4,$5);
        $date_of_auction=&data_clean($date_of_auction);
        $market=&data_clean($market);
        $type=&data_clean($type);
        $price_per_kg=&data_clean($price_per_kg);
        open(FH,">>$filename");
        print FH "$curdatetime\t$sno\t$date_of_auction\t$market\t$type\t$price_per_kg\t$ips\t$Cache_name\n";
        close FH;
    }
    
    if($HomeContent=~m/<a[^>]*?href="([^"]+?)"[^>]*?>\s*Next\s*<\/a>/is)
    {
        my $next_url="$starting_page$1";
        print "\nNEXT URL  ::  $next_url\n";
        my %headers=('accept'=>'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7","accept-language'=>'en-US,en;q=0.9","connection'=>'keep-alive","host'=>'www.indianspices.com","sec-ch-ua'=>'"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"","sec-ch-ua-mobile'=>'?0","sec-ch-ua-platform'=>'"Windows"","sec-fetch-dest'=>'document","sec-fetch-mode'=>'navigate","sec-fetch-site'=>'none","sec-fetch-user'=>'?1","upgrade-insecure-requests'=>'1","user-agent'=>'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36');
        my $nextcontent=&GetContent($next_url,'GET',\%headers,$home_url);
        my $next_Cache_name="Next_Content_$page.html";
        open(FH,">$next_Cache_name");
        print FH $nextcontent;
        close FH;
        $home_url=$next_url;
        $HomeContent=$nextcontent;    
        $Cache_name=$next_Cache_name;
        $page++;
        goto start;
    }

sub data_clean
{
	my $var=shift;
	$var=~s/\n/ /igs;
	$var=~s/\t/ /igs;
	$var=~s/\r/ /igs;
	$var=~s/\s+/ /igs;
	$var=~s/^\s+//igs;
	$var=~s/\s+$//igs;
	return $var;

}

sub get_public_ip {
    my $ua = LWP::UserAgent->new(timeout => 10);

    my $res = $ua->get('https://api.ipify.org');

    return $res->is_success ? $res->decoded_content : undef;
}


	

sub GetContent
{
	my($g_url,$method,$parameter,$referer)=@_;

	my ($req,$res,$code); 
	my $debug=0;
	my $loc_count=1;
	my $curdatetime=DateTime->now();
	my $dt1 = $parser->parse_datetime($curdatetime) or die;
	start1:
	sleep(1);
	$req= HTTP::Request->new($method => $g_url);
	if($method=~m/POST/is)
	{
		$req->content($parameter);
		$req->header('Content-Type'=>'application/x-www-form-urlencoded');
	}
	$res = $ua->request($req);
	$cookie_jar->extract_cookies($res);
	$cookie_jar->save;
	$cookie_jar->add_cookie_header($req);
	$code=$res->code();	
	print "CODE  ::  $code\n";
	my $ST_Desc;
	$ST_Desc = "Success" if($code =~m/20/is);
	$ST_Desc = "Redirect" if($code =~m/30/is);
	$ST_Desc = "Incorrect URL" if($code =~m/40/is);
	$ST_Desc = "Net Failure" if($code =~m/50/is);
	
	my $curdatetime=DateTime->now();
	my $dt2 = $parser->parse_datetime($curdatetime) or die;
	my $diff = $dt2 - $dt1;
	my $run_time=$diff->seconds."s";   ####Ping duration####
	print "\n\nRUN_TIME-->>>$run_time\n\n";
	if($code=~m/40/is)
	{
		print "\nURL missing .Page not found\n";
		if($debug<3)
		{
			sleep(60);
			$debug++;
			goto start1;
		}
		return;
	}
	elsif($code=~m/50/is)
	{
		$req=HTTP::Request->new(GET=>"http://www.cpan.org");
		$req->header("Content-Type"=> "application/x-www-form-urlencoded");
		$res=$ua->request($req);
		my $code1=$res->code();
	 	print "\nNET_CHECK :$code1\n";
		if($code1=~m/50/is)
		{
			print "\nNet Failure";
			sleep(0);
			goto start1;
		}
		elsif($code1=~m/20/is)
		{
			if($debug==3)
			{
				print "\nURL missing .Page not found\n";
				open(FH,">>URLMissingError.txt");
				print FH "Code  ::  $code\nURL  ::  $g_url\n";
				close FH;
				return;
			}
			else
			{	
				print "\nDEBUG :: $code1 :: $debug\n";
			}
			$debug++;
			print "\nDEBUG :: $debug\n";
			sleep(0);
			goto start1;
		}
	}
	elsif($code=~m/30/is)
	{
		if($loc_count>=4)
		{
			open(FH,">>URLMissingError.txt");
			print FH "Code  ::  $code\nURL  ::  $g_url\n";
			close FH;
			return;
		}
		$loc_count++;
		my $location=$res->header('location');
		my $loc_url=URI::URL->new_abs($location,$g_url);
		print "Redirect URL  ::  $loc_url\n";
		($g_url,$method)=($loc_url,'GET');
		goto start1;
	}
	elsif($code=~m/20/is)
	{
		my $g_con=$res->content;
		return $g_con;
	}
	my $g_con=$res->content;
	return $g_con;
}
