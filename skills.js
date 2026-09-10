/* =====================================================================
   Career Growth — Skills tab content

   Edit freely. Each skill takes:
     name   short title
     why    one line on why it matters at a senior finance level
     links  [{ title, url, kind }]  kind shows as a small tag

   A note on the links: YouTube video IDs die over time and a dead link
   in a study plan is worse than no link. So video links are precise
   pre-loaded searches that always resolve, with the channel worth
   looking for named in the title. Documentation links go to official
   pages. When you find a course you like, replace the search link with
   the real URL.
   ===================================================================== */

const yt = q => 'https://www.youtube.com/results?search_query=' + encodeURIComponent(q);

const SKILLS = [

  /* ------------------------------------------------------------------ */
  {
    group: 'Data and analytics',
    note: 'The difference between requesting a report and interrogating the data yourself. This is the stack that scales when the dataset stops fitting in Excel.',
    items: [

      {
        name: 'Power BI',
        why: 'The highest return per hour on this list for a finance lead. Turns monthly reporting into a live dashboard the board can open themselves.',
        links: [
          { title: 'Full beginner-to-advanced course (freeCodeCamp)', url: yt('Power BI full course for beginners freeCodeCamp'), kind: 'Course' },
          { title: 'Guy in a Cube — weekly DAX and modelling tips', url: yt('Guy in a Cube Power BI'), kind: 'Channel' },
          { title: 'DAX for financial measures and time intelligence', url: yt('DAX time intelligence YTD financial reporting Power BI'), kind: 'Topic' },
          { title: 'Microsoft Learn — official Power BI path', url: 'https://learn.microsoft.com/en-us/training/powerplatform/power-bi', kind: 'Docs' }
        ]
      },

      {
        name: 'Power Query',
        why: 'Kills the monthly copy-paste ritual. Learn this before Power BI — it is the cleaning layer underneath both Excel and BI, and it pays off immediately.',
        links: [
          { title: 'Power Query full tutorial for Excel users', url: yt('Power Query Excel full tutorial beginner to advanced'), kind: 'Course' },
          { title: 'Merging, appending and unpivoting messy reports', url: yt('Power Query unpivot merge append tutorial'), kind: 'Topic' },
          { title: 'M language basics for custom columns', url: yt('Power Query M language tutorial'), kind: 'Topic' },
          { title: 'Microsoft — official Power Query documentation', url: 'https://learn.microsoft.com/en-us/power-query/', kind: 'Docs' }
        ]
      },

      {
        name: 'SQL',
        why: 'Lets you pull from the accounting database directly instead of waiting on IT for an extract. The single most portable technical skill in finance.',
        links: [
          { title: 'Full SQL course for beginners (freeCodeCamp)', url: yt('SQL full course for beginners freeCodeCamp'), kind: 'Course' },
          { title: 'Joins, subqueries and window functions explained', url: yt('SQL joins subqueries window functions tutorial'), kind: 'Topic' },
          { title: 'SQL for data analysis — Alex The Analyst', url: yt('Alex The Analyst SQL for data analytics'), kind: 'Channel' },
          { title: 'W3Schools — SQL reference and live editor', url: 'https://www.w3schools.com/sql/', kind: 'Practice' }
        ]
      },

      {
        name: 'Python',
        why: 'Where analysis goes when it outgrows a spreadsheet. For audit work the real prize is testing a full population rather than a sample.',
        links: [
          { title: 'Python for beginners — full course', url: yt('Python full course for beginners freeCodeCamp'), kind: 'Course' },
          { title: 'Corey Schafer — clear, unhurried Python series', url: yt('Corey Schafer Python tutorial'), kind: 'Channel' },
          { title: 'Pandas for data analysis', url: yt('pandas python data analysis full tutorial'), kind: 'Topic' },
          { title: 'Automating Excel reports with openpyxl', url: yt('python automate excel reports openpyxl tutorial'), kind: 'Topic' },
          { title: 'Automate the Boring Stuff — free online book', url: 'https://automatetheboringstuff.com/', kind: 'Book' }
        ]
      },

      {
        name: 'R',
        why: 'Stronger than Python for statistics and audit sampling. Worth it if you do analytical review, forecasting or regression work rather than general automation.',
        links: [
          { title: 'R programming full course for beginners', url: yt('R programming full course for beginners freeCodeCamp'), kind: 'Course' },
          { title: 'Tidyverse and dplyr for data wrangling', url: yt('R tidyverse dplyr tutorial data wrangling'), kind: 'Topic' },
          { title: 'R for Data Science — free online book', url: 'https://r4ds.hadley.nz/', kind: 'Book' }
        ]
      },

      {
        name: 'Data analysis foundations',
        why: 'The reasoning underneath the tools. Knowing which question the data can actually answer matters more than knowing the syntax.',
        links: [
          { title: 'Complete data analyst roadmap', url: yt('data analyst full course roadmap beginner'), kind: 'Course' },
          { title: 'Statistics for data analysis', url: yt('statistics for data analysis full course'), kind: 'Topic' },
          { title: 'Financial statement analysis with data tools', url: yt('financial statement analysis excel dashboard tutorial'), kind: 'Topic' },
          { title: 'Data visualisation — choosing the right chart', url: yt('data visualization best practices choosing charts'), kind: 'Topic' }
        ]
      }
    ]
  },

  /* ------------------------------------------------------------------ */
  {
    group: 'Accounting systems and ERP',
    note: 'Software you will be asked to select, implement, audit or sign off on. Knowing the control environment inside each one is the senior-level skill, not data entry.',
    items: [

      {
        name: 'SAP (FICO)',
        why: 'The system behind most large clients. Understanding the FI/CO module structure changes how you scope an audit and where you look for control weaknesses.',
        links: [
          { title: 'SAP FICO full course for beginners', url: yt('SAP FICO full course for beginners'), kind: 'Course' },
          { title: 'SAP S/4HANA finance overview', url: yt('SAP S4HANA finance overview tutorial'), kind: 'Topic' },
          { title: 'SAP Learning — official free training', url: 'https://learning.sap.com/', kind: 'Docs' }
        ]
      },

      {
        name: 'QuickBooks',
        why: 'Dominant among smaller clients. Fast to learn, and the certification is a credible line on a profile for advisory work.',
        links: [
          { title: 'QuickBooks Online complete tutorial', url: yt('QuickBooks Online full tutorial for beginners'), kind: 'Course' },
          { title: 'Month-end close and reconciliation in QuickBooks', url: yt('QuickBooks month end close reconciliation tutorial'), kind: 'Topic' },
          { title: 'Intuit — official training and certification', url: 'https://quickbooks.intuit.com/learn-support/', kind: 'Docs' }
        ]
      },

      {
        name: 'Xero',
        why: 'The main alternative to QuickBooks, and stronger in some markets. Its certification is free, which makes the effort-to-credential ratio excellent.',
        links: [
          { title: 'Xero complete tutorial for accountants', url: yt('Xero accounting software full tutorial for accountants'), kind: 'Course' },
          { title: 'Bank reconciliation and rules in Xero', url: yt('Xero bank reconciliation rules tutorial'), kind: 'Topic' },
          { title: 'Xero Central — official learning and certification', url: 'https://central.xero.com/', kind: 'Docs' }
        ]
      },

      {
        name: 'Excel at an advanced level',
        why: 'Still the language every finance function actually speaks. The gap between good and excellent here is worth more than a new tool entirely.',
        links: [
          { title: 'Advanced Excel full course', url: yt('advanced excel full course for finance professionals'), kind: 'Course' },
          { title: 'Financial modelling from scratch', url: yt('financial modelling excel full course three statement model'), kind: 'Topic' },
          { title: 'INDEX MATCH, XLOOKUP and dynamic arrays', url: yt('XLOOKUP INDEX MATCH dynamic arrays excel tutorial'), kind: 'Topic' },
          { title: 'ExcelIsFun — deep, free, enormous archive', url: yt('ExcelIsFun advanced excel'), kind: 'Channel' }
        ]
      }
    ]
  },

  /* ------------------------------------------------------------------ */
  {
    group: 'Communication and leadership',
    note: 'What decides whether your technical work changes a decision. At a senior level this is usually the binding constraint, not the accounting.',
    items: [

      {
        name: 'Public speaking',
        why: 'Presenting to a board is a different skill from knowing the numbers. Structure and delivery are learnable, and the improvement is fast once you start.',
        links: [
          { title: 'Public speaking complete course', url: yt('public speaking full course confidence delivery'), kind: 'Course' },
          { title: 'How to open and close a presentation', url: yt('how to start and end a presentation powerfully'), kind: 'Topic' },
          { title: 'Managing nerves and filler words', url: yt('how to stop saying um filler words speaking'), kind: 'Topic' },
          { title: 'Toastmasters — find a local practice club', url: 'https://www.toastmasters.org/find-a-club', kind: 'Practice' }
        ]
      },

      {
        name: 'Executive presence',
        why: 'Being heard in a room where you are not the most senior person. Largely about how you frame a position and handle challenge, not about volume.',
        links: [
          { title: 'Executive presence and gravitas', url: yt('executive presence gravitas leadership communication'), kind: 'Course' },
          { title: 'Communicating with senior stakeholders', url: yt('communicating with executives senior stakeholders'), kind: 'Topic' },
          { title: 'Presenting financial results to non-finance people', url: yt('presenting financial results to non finance audience'), kind: 'Topic' }
        ]
      },

      {
        name: 'Negotiation',
        why: 'Fee discussions, audit scope, vendor contracts, your own compensation. Underinvested in by most accountants relative to how often it comes up.',
        links: [
          { title: 'Negotiation skills full course', url: yt('negotiation skills full course business'), kind: 'Course' },
          { title: 'Chris Voss — tactical empathy and calibrated questions', url: yt('Chris Voss negotiation tactical empathy'), kind: 'Channel' },
          { title: 'Salary negotiation for professionals', url: yt('salary negotiation strategy professional'), kind: 'Topic' }
        ]
      },

      {
        name: 'Personality development',
        why: 'The habits underneath everything else — how you handle conflict, take feedback and hold a room. Slow to build and hard to fake.',
        links: [
          { title: 'Personality development complete series', url: yt('personality development full course communication confidence'), kind: 'Course' },
          { title: 'Emotional intelligence at work', url: yt('emotional intelligence at work full course'), kind: 'Topic' },
          { title: 'Handling difficult conversations', url: yt('how to handle difficult conversations at work'), kind: 'Topic' },
          { title: 'Body language and first impressions', url: yt('body language professional first impressions'), kind: 'Topic' }
        ]
      },

      {
        name: 'Managing and delegating',
        why: 'The transition from doing the work to being accountable for other people doing it. The most common place a technically strong career stalls.',
        links: [
          { title: 'First-time manager complete guide', url: yt('first time manager complete guide leadership'), kind: 'Course' },
          { title: 'Delegation without losing control of quality', url: yt('how to delegate effectively manager'), kind: 'Topic' },
          { title: 'Giving feedback that actually lands', url: yt('how to give constructive feedback to your team'), kind: 'Topic' },
          { title: 'Running a meeting people do not resent', url: yt('how to run effective meetings'), kind: 'Topic' }
        ]
      },

      {
        name: 'Writing for decision makers',
        why: 'A board paper that gets read to the end is a skill in itself. Conclusion first, evidence after — the opposite of how audit files are written.',
        links: [
          { title: 'Business writing complete course', url: yt('business writing full course professional'), kind: 'Course' },
          { title: 'The pyramid principle for structuring arguments', url: yt('Barbara Minto pyramid principle explained'), kind: 'Topic' },
          { title: 'Writing executive summaries', url: yt('how to write an executive summary board report'), kind: 'Topic' }
        ]
      }
    ]
  }
];
