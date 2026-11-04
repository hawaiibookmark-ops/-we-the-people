"use client";

import { useEffect, useState } from "react";
import { siteOrigin } from "@/lib/config";

export default function ProPage() {
  const [returnUrl, setReturnUrl] = useState("https://getwethepeople.com/pro/");
  useEffect(() => {
    setReturnUrl(`${siteOrigin()}/pro/`);
  }, []);

  return (
    <section className="hero">
      <p className="kicker">Early Supporter</p>
      <h1>$5/month. Lookup stays free.</h1>
      <p className="lede">
        Early Supporter is a PayPal subscription that helps keep We The People running. No ads
        are sold. Donor lists and user data are not sold.
      </p>
      <div className="pro-box">
        <h2>What exists today (free for everyone)</h2>
        <ul>
          <li>ZIP, address and island lookup of your races and candidates</li>
          <li>Federal voting records from official roll calls</li>
          <li>Donor data from the FEC and state campaign finance agencies</li>
          <li>PAC, outside and party money</li>
          <li>Hawaii county council records</li>
          <li>Every fact cited with its official source and date</li>
        </ul>
        <p>
          Supporting does not unlock extra features. Upcoming features are not promised.
        </p>
        <p>
          <strong>Refunds:</strong> cancel anytime in PayPal; email hawaiibookmark@gmail.com within
          30 days for a full refund of any charge.
        </p>
        <form action="https://www.paypal.com/cgi-bin/webscr" method="post" target="_blank">
          <input type="hidden" name="cmd" value="_xclick-subscriptions" />
          <input type="hidden" name="business" value="hawaiibookmark@gmail.com" />
          <input type="hidden" name="item_name" value="We The People Early Supporter" />
          <input type="hidden" name="no_note" value="1" />
          <input type="hidden" name="currency_code" value="USD" />
          <input type="hidden" name="a3" value="5.00" />
          <input type="hidden" name="p3" value="1" />
          <input type="hidden" name="t3" value="M" />
          <input type="hidden" name="src" value="1" />
          <input type="hidden" name="sra" value="1" />
          <input type="hidden" name="return" value={returnUrl} />
          <button className="btn" type="submit">
            Subscribe $5/month via PayPal
          </button>
        </form>
        <p className="muted" style={{ color: "#d9cbb3" }}>
          PayPal cmd=_xclick-subscriptions · hawaiibookmark@gmail.com · $5.00 USD monthly
        </p>
      </div>
    </section>
  );
}
