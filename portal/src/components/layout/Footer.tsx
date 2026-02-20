import Link from "next/link";
import { Mail, Phone, ExternalLink } from "lucide-react";

export default function Footer() {
  const companyName = process.env.NEXT_PUBLIC_COMPANY_NAME ?? "RES, LLC";
  const supportEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL ?? "it@res-llc.com";

  return (
    <footer className="bg-navy text-white mt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 rounded bg-gold flex items-center justify-center">
                <span className="text-navy font-bold text-sm">R</span>
              </div>
              <span className="font-semibold text-lg">RES Connect</span>
            </div>
            <p className="text-gray-300 text-sm leading-relaxed">
              AI-powered HR knowledge base for {companyName} employees. Find policies, benefits, and answers instantly.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="font-semibold text-gold mb-3">Quick Links</h3>
            <ul className="space-y-2 text-sm text-gray-300">
              {[
                { label: "HR Handbook", href: "/docs/doc-001" },
                { label: "Benefits Portal", href: "/docs/doc-003" },
                { label: "Time Off Policy", href: "/docs/doc-002" },
                { label: "Org Chart", href: "/docs/doc-005" },
                { label: "IT Help Desk", href: "/docs/doc-006" },
              ].map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="hover:text-gold transition-colors">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h3 className="font-semibold text-gold mb-3">IT Support</h3>
            <ul className="space-y-3 text-sm text-gray-300">
              <li className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-gold flex-shrink-0" />
                <a href={`mailto:${supportEmail}`} className="hover:text-gold transition-colors">
                  {supportEmail}
                </a>
              </li>
              <li className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-gold flex-shrink-0" />
                <a href="tel:+15555550100" className="hover:text-gold transition-colors">
                  (555) 555-0100
                </a>
              </li>
              <li className="flex items-center gap-2">
                <ExternalLink className="h-4 w-4 text-gold flex-shrink-0" />
                <a href="https://helpdesk.res-llc.com" target="_blank" rel="noopener noreferrer" className="hover:text-gold transition-colors">
                  Submit a Ticket
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-gray-400">
          <p>&copy; {new Date().getFullYear()} {companyName}. All rights reserved.</p>
          <p>RES Connect v1.0 — Internal use only</p>
        </div>
      </div>
    </footer>
  );
}
