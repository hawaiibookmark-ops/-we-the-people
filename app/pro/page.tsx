export default function ProPage() {
  return (
    <section className="hero">
      <p className="kicker">Founding Pro</p>
      <h1>$5/month. Lookup stays free.</h1>
      <p className="lede">
        Founding Pro is a PayPal subscription for people who want extras on top of the public
        hub. Candidate ads are not sold. Donor lists and user data are not sold.
      </p>
      <div className="pro-box">
        <h2>What Founding Pro is for</h2>
        <ul>
          <li>Election alerts</li>
          <li>A saved district</li>
          <li>CSV export</li>
          <li>Monitored race chat</li>
        </ul>
        <p>
          Those extras are on a founding waitlist until they ship. Subscribing holds a founding
          rate and a place in line. The ZIP/address/island lookup on this site remains free.
        </p>
        <form action="https://www.paypal.com/cgi-bin/webscr" method="post" target="_blank">
          <input type="hidden" name="cmd" value="_xclick-subscriptions" />
          <input type="hidden" name="business" value="hawaiibookmark@gmail.com" />
          <input type="hidden" name="item_name" value="We The People Founding Pro" />
          <input type="hidden" name="no_note" value="1" />
          <input type="hidden" name="currency_code" value="USD" />
          <input type="hidden" name="a3" value="5.00" />
          <input type="hidden" name="p3" value="1" />
          <input type="hidden" name="t3" value="M" />
          <input type="hidden" name="src" value="1" />
          <input type="hidden" name="sra" value="1" />
          <input type="hidden" name="return" value="https://hawaiibookmark-ops.github.io/-we-the-people/pro/" />
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
