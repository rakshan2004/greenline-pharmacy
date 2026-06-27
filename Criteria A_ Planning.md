# Criteria A: Planning

## Scenario

Mr. Arjun Mehta, my client, operates Greenline Pharmacy, which is a retail medical store. In addition to this, he wholesales medicines to small local clinics. Not only does Mr. Mehta run the counter for his store, but he has also been managing inventory by keeping records of his stock, his suppliers and receivables from the clinics he supplies to.

When I interviewed him, he got right to the point of how disorganized his business had become: "Right now I track my stock, my suppliers and what the clinics owe me using a notebook and an Excel sheet. Half the time I only find out a medicine has expired when a customer asks for it and it's already gone bad" (Appendix 1, first interview, Point 3). He continued on to another problem – "I lose track of payments the clinics owe me, and I've got no real way of knowing which medicines are running low until they're already out" (Appendix 1, Point 4).

When questioned about what he would like to see from a system, he gave a rather straightforward response: "Something easy to use, since I'm not great with computers, and something that just shows me reports when I need them instead of me sitting there adding things up myself" (Appendix 1, Point 5). He also mentioned budget being an issue – "I can't really spend much on software right now, between rent and stock costs" (Appendix 1, Point 6). Budget ended up becoming a large factor for my decisions below.

## Rationale for Proposed Solution

Mr. Mehta's real problem is not the pharmacy itself but that fact that he has been spending hours upon hours on something that his computer should have been doing for him and even then managed to get it wrong as well. A good system would completely off load that for him. Since Mr. Mehta explicitly said that he has had no practice whatsoever using a computer, i thought CLI was totally out of the question and even a menu system didn't seem flexible enough. So a WIMP system was the logical choice since he could fill forms by click and click and remember absolutely nothing apart from remembering what each button would do to fill in the details of any medicine as long as he can follow forms. For the front end i decided upon using Python 3 with the Tkinter GUI toolkit, developed in the PyCharm Community IDE, and for the back-end i will use SQLite, which is accessed through the `sqlite3` module that is built directly into Python so that no separate database server or external driver is required. The whole system will be freeware since Mr Mehta said to minimize the cost and so the expenses are all spent on my labour. It is important to notice that i chose a relational database over a simple flat-file structure so that records can be linked, without redundant copying, so that data consistency can be maintained even while modifying or deleting records.

## Success Criteria

They then logon with username and password, there is validation at this point and this was specifically requested by him. "Is it possible to put some kind of protection on the passwords as i dont want staff/competitors seeing our prices for the suppliers." Appendix 1 point 7.

Medical representatives will able to create/edit/remove records for all type of medicines and from all suppliers with credit information and paid/not paid records to their accounts. They can add, edit and delete records of their clinic account, including of credit and paid/not paid details.

The system generates reports for each clinic based on amount owed by, it was an important part of the query "How will I know what each clinic still owes me?" (Appendix 1, point 8).

Profit and loss reports can be run for a selected date range.

The system checks data whenever it is entered – e.g., the user cannot have a negative number of stock, or leave a mandatory field blank.

Any drugs approaching expiration are automatically highlighted, and the answer is "How will I know what stock is about to expire or running low?" (Appendix 1, point 9).

Reports detailing total current stock by supplier can also be produced.

The stock can be searched by supplier, medicine, or expiration date, and the answer to "Will it be hard to search for a particular medicine or supplier?" is provided by this feature.

Sales and stock data can be displayed in chart format (pie charts, bar charts) to facilitate quick analysis.

Word Count: 503
